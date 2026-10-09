"""Everything that creates or changes an order, and the reads the pages need. The rules are in rules.py (pure); this layer applies them to
the database, never trusting a form, a price on a page or a browser: the item, its price and value, the upgrades, the limits, the stock,
and the balance are all read again here, under locks.

Locks, always in this order: the person's Profile row (the same lock the ledger and projects take, so one person is serialized), then
the shop item rows (base and upgrades, by id), then the order row. SQLite ignores select_for_update, so the database is in IMMEDIATE
mode (settings.py) which serializes writers; on Postgres the row locks do the work.

The money: placing an order debits the ledger under the key `order:{id}` in the same transaction; rejecting, cancelling or refunding
credits it back under `order:{id}:refund`, once (the status moves only forward, and the ledger refuses a key twice). Stock follows the
same moves. A second post of the same page (same nonce) places nothing and returns the order that page already made.
"""
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import F, Q, Sum
from django.utils import timezone

from audit import services as audit
from ledger import rules as ledger_rules
from ledger import services as ledger
from orders import rules
from orders.models import Order, OrderLine
from pages.live import live
from projects import services as project_services
from shop.models import ShopItem
from submissions.services import holds_ribbon_user

GONE = "That isn't on my shelf any more, dear."
NEEDS_PROOF = "Show me what you're buying, dear: the link and a screenshot of the cart."
NEEDS_LINK = "Show me what you're buying, dear: the link to it."
NEEDS_REF = "Paste the reference of the grant you issued before you mark it fulfilled."
BAD_PAGE = "That page has gone stale, dear. Open it again."
OWN_ORDER = "You cannot decide on your own order. Ask another staff member."


# reads the pages use

def gettable(slug, ribbon=False):
    """The base grant with this slug, active: an upgrade is never sold alone, so one gets None. Upgrades come along as `live_upgrades`.
    A ribbon only grant (or upgrade) is found only when `ribbon` says the person holds a Blue Ribbon: for anybody else it is None, like an unknown slug."""
    item = ShopItem.objects.visible(ribbon).filter(slug=slug, base_item__isnull=True).first()
    if item is not None:
        item.live_upgrades = list(item.upgrades.visible(ribbon))
    return item


def held(user, item_id):
    """How many of this base grant the person has in orders that are not rejected, refunded or cancelled."""
    total = OrderLine.objects.filter(order__user=user, order__status__in=rules.LIVE, item_id=item_id, upgrade=False).aggregate(total=Sum("quantity"))["total"]
    return total or 0


def already_placed(user, nonce):
    """Has this page (its nonce) already made an order for this person? Then posting it again places nothing."""
    return bool(nonce) and Order.objects.filter(user=user, nonce=nonce).exists()


# placing an order

def refuse(problem):
    if problem:
        raise ValidationError(problem)


def line_of(item, quantity, upgrade=False):
    return rules.Line(item.pk, quantity, item.effective_cookies, item.usd_value, upgrade)


def locked_items(item_id, ribbon, lock=True):
    """The base grant (active, never an upgrade) and its active upgrades, rows locked, by id (`lock` off: just read, for precheck, which is not
    in a transaction). (None, {}) when the grant is gone, or is ribbon only and the person holds no Blue Ribbon (`ribbon`): it is gone for
    them, whatever the browser said."""
    rows = ShopItem.objects.visible(ribbon).filter(Q(pk=item_id) | Q(base_item_id=item_id)).order_by("pk")
    rows = list(rows.select_for_update() if lock else rows)
    base = next((row for row in rows if row.pk == item_id and row.base_item_id is None), None)
    return base, {row.pk: row for row in rows if base and row.base_item_id == base.pk}


def chosen_upgrades(base, upgrades, counts):
    """The (upgrade item, count) pairs a person asked for, each checked: it belongs to this base, the count is sane, the stock lasts."""
    chosen = []
    for item_id, count in sorted(counts.items()):
        if count == 0:
            continue
        upgrade = upgrades.get(item_id)
        refuse(rules.upgrade_problem(base.pk, upgrade.base_item_id if upgrade else None))
        refuse(rules.upgrade_count_problem(count, upgrade.max_per_user, upgrade.name) or rules.stock_problem(upgrade.stock, count))
        chosen.append((upgrade, count))
    return chosen


def save_lines(order, offer):
    for line in offer.lines:
        OrderLine.objects.create(order=order, item_id=line.item_id, quantity=line.quantity, unit_cookies=line.unit_cookies, unit_value=line.unit_value, upgrade=line.upgrade)


def take_stock(offer):
    """Take what was ordered from the shelves that count their stock (an empty stock is unlimited and stays so)."""
    for line in offer.lines:
        ShopItem.objects.filter(pk=line.item_id, stock__isnull=False).update(stock=F("stock") - line.quantity)


def priced(user, base, counts, quantity):
    """The offer for a base grant and its chosen upgrades, once the per-person limit, the stock and the balance allow it: ValidationError with a
    sentence for the person otherwise. Reads only; place_order calls it under locks, precheck without."""
    refuse(rules.limit_problem(base.stackable, base.max_per_user, held(user, base.pk), quantity) or rules.stock_problem(base.stock, quantity))
    for upgrade, count in counts:
        refuse(rules.upgrade_count_problem(count, upgrade.max_per_user, upgrade.name) or rules.stock_problem(upgrade.stock, count))
    offer = rules.price([line_of(base, quantity)] + [line_of(up, count, upgrade=True) for up, count in counts])
    refuse(rules.afford_problem(ledger.balance(user), offer.cookies))
    return offer


def precheck(user, item_id, *, quantity=1, upgrades=None):
    """The cheap checks of place_order (the grant is still on the shelf, the upgrades, the limit, the stock, the balance), made without locks
    BEFORE the screenshot is decoded, which is the costly part (orders/forms.py). Only a fast refusal, never a promise: place_order checks
    everything again under locks. ValidationError with a sentence for the person."""
    base, upgrade_items = locked_items(item_id, holds_ribbon_user(user), lock=False)
    refuse(None if base else GONE)
    priced(user, base, chosen_upgrades(base, upgrade_items, upgrades or {}), quantity)


@transaction.atomic
def place_order(user, item_id, *, nonce, quantity=1, upgrades=None, product_url="", user_note="", cart_screenshot=None):
    """Place an order for the grant `item_id` (a base item) and take the cookies, or raise ValidationError with a sentence for the person.

    Everything is checked here again under locks, whatever the form showed. `nonce` is the page's: a second post of it returns the first
    order. A grant takes a quantity and the upgrades asked for. `cart_screenshot` is a ContentFile already sanitised by submissions/images.py."""
    refuse(None if rules.NONCE.fullmatch(nonce or "") else BAD_PAGE)
    project_services.lock_person(user)
    placed = Order.objects.filter(user=user, nonce=nonce).first()
    if placed:
        return placed
    base, upgrade_items = locked_items(item_id, holds_ribbon_user(user))
    refuse(None if base else GONE)
    proves = base.kind == ShopItem.Kind.GRANT
    counts = chosen_upgrades(base, upgrade_items, upgrades or {})
    wants_picture = proves and live().ORDER_CART_SCREENSHOT      # read here, not from the form: with it off no picture is ever stored
    refuse((NEEDS_PROOF if wants_picture else NEEDS_LINK) if proves and not (product_url and (cart_screenshot or not wants_picture)) else "")
    refuse(rules.url_problem(product_url) if proves else "")
    offer = priced(user, base, counts, quantity)
    order = Order(user=user, item=base, nonce=nonce, total_cookies=offer.cookies, total_value=offer.value,
                  product_url=product_url.strip() if proves else "", user_note=user_note, cart_screenshot=(cart_screenshot or "") if wants_picture else "")
    order.full_clean(exclude=["cart_screenshot"])
    order.save()
    save_lines(order, offer)
    ledger.debit(user, offer.cookies, reason=f"Grant: {base.name} (order {order.pk})"[:200], key=f"order:{order.pk}")
    take_stock(offer)
    audit.record(
        "order.place",
        actor=user,
        subject=user,
        target=order,
        details={
            "item": base.pk,
            "lines": [[line.item_id, line.quantity] for line in offer.lines],
            "total_cookies": int(order.total_cookies),
            "total_value": str(order.total_value),
        },
    )
    return order


# changing an order: staff approve, reject, fulfil and refund; a person takes back one nobody has looked at

def give_back(order):
    """Cookies and stock go back to where they came from. Called once, when an order moves into a status that gives back."""
    ledger.credit(order.user, order.total_cookies, reason=f"Refund: {order.item.name} (order {order.pk})"[:200], key=f"order:{order.pk}:refund", kind=ledger_rules.REFUND)
    for line in order.lines.all():
        ShopItem.objects.filter(pk=line.item_id, stock__isnull=False).update(stock=F("stock") + line.quantity)


def refuse_own(by, order):
    """Staff (`by`) never decide on their own order, whoever they are: ValidationError (OWN_ORDER), nothing saved. The person taking back their
    own pending order is not staff action (`owner`, no `by`) and is not touched. The same rule as reviewing your own project."""
    refuse(OWN_ORDER if by is not None and by.pk == order.user_id else None)


@transaction.atomic
def move(order_id, to, *, by=None, grant_ref=None, owner=None):
    """Move an order to a new status, once and only forward (rules.TRANSITIONS). Into rejected, cancelled or refunded the cookies and the
    stock go back (exactly once: the move happens once and the ledger refuses the refund key twice). Fulfilled needs the grant reference.
    `owner` restricts it to that person's own order. ValidationError with a sentence when it cannot be done, None when there is no such
    order (or it is not the owner's). Moving to the status it already has changes nothing. `by` (staff) is refused their own order (refuse_own)."""
    found = Order.objects.select_related("user").filter(pk=order_id, **({"user": owner} if owner else {})).first()
    if found is None:
        return None
    refuse_own(by, found)
    project_services.lock_person(found.user)
    order = Order.objects.select_for_update().select_related("user", "item").get(pk=order_id)
    if order.status == to:
        return order
    refuse(None if rules.can_move(order.status, to) else f"An order that is {rules.LABELS[order.status].lower()} can't become {rules.LABELS[to].lower()}.")
    old_status = order.status
    if grant_ref is not None:
        order.grant_ref = grant_ref.strip()
    refuse(NEEDS_REF if to == rules.FULFILLED and not order.grant_ref else "")
    if to in rules.GIVES_BACK:
        give_back(order)
    order.status = to
    if by is not None:
        order.reviewed_by, order.reviewed_at = by, timezone.now()
    order.save(update_fields=["status", "grant_ref", "reviewed_by", "reviewed_at"])
    audit.record(
        "order.move",
        actor=by or owner,
        subject=order.user,
        target=order,
        details={
            "from": old_status,
            "to": to,
            "has_ref": bool(order.grant_ref),
        },
    )
    return order


def approve(order_id, *, by):
    return move(order_id, rules.APPROVED, by=by)


def reject(order_id, *, by):
    return move(order_id, rules.REJECTED, by=by)


def refund(order_id, *, by):
    return move(order_id, rules.REFUNDED, by=by)


def fulfil(order_id, grant_ref, *, by):
    return move(order_id, rules.FULFILLED, by=by, grant_ref=grant_ref)


def cancel(user, order_id):
    """A person takes back their own order, only while it is still pending: nobody has looked at it yet."""
    return move(order_id, rules.CANCELLED, owner=user)


@transaction.atomic
def review(order, *, by):
    """Save what staff edited on `order` (the admin form put it on the object): the notes, the grant reference and, if it changed, the status,
    which goes through move() so a rejection refunds. Only those fields are written, so a stale form cannot touch anything else. Staff cannot
    save their own order at all (refuse_own): not the status, not the notes, not the reference."""
    stored = Order.objects.get(pk=order.pk)
    refuse_own(by, stored)
    if order.status != stored.status:
        move(order.pk, order.status, by=by, grant_ref=order.grant_ref)
    current = Order.objects.select_for_update().get(pk=order.pk)
    new_grant_ref = (order.grant_ref or "").strip()
    changed_fields = []
    if current.public_note != (order.public_note or ""):
        changed_fields.append("public_note")
    if current.internal_note != (order.internal_note or ""):
        changed_fields.append("internal_note")
    if current.grant_ref != new_grant_ref:
        changed_fields.append("grant_ref")
    if changed_fields:
        current.public_note, current.internal_note, current.grant_ref = order.public_note, order.internal_note, new_grant_ref
        current.save(update_fields=["public_note", "internal_note", "grant_ref"])
        audit.record(
            "order.review",
            actor=by,
            subject=current.user,
            target=current,
            details={"fields": changed_fields},
        )
    return current
