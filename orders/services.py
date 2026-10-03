"""Everything that creates or changes an order, and the reads the pages need. The rules are in rules.py (pure); this layer applies them to
the database, never trusting a form, a price on a page or a browser: the item, its price and value, the upgrades, the limits, the stock,
the project and the balance are all read again here, under locks.

Locks, always in this order: the person's Profile row (the same lock the ledger and projects take, so one person is serialized), then
the shop item rows (base and upgrades, by id), then the order row. SQLite ignores select_for_update, so the database is in IMMEDIATE
mode (settings.py) which serializes writers; on Postgres the row locks do the work.

The money: placing an order debits the ledger under the key `order:{id}` in the same transaction; rejecting, cancelling or refunding
credits it back under `order:{id}:refund`, once (the status moves only forward, and the ledger refuses a key twice). Stock follows the
same moves. A second post of the same page (same nonce) places nothing and returns the order that page already made.
"""
from typing import NamedTuple

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import F, Q, Sum
from django.utils import timezone

from ledger import rules as ledger_rules
from ledger import services as ledger
from orders import rules
from orders.models import Order, OrderLine, OrderPart
from projects import rules as project_rules
from projects import services as project_services
from projects.models import Category, Project
from shop.models import ShopItem
from submissions import rules as submission_rules

GONE = "That isn't on my shelf any more, dear."
NEEDS_PROOF = "Show me what you're buying, dear: the link and a screenshot of the cart."
NEEDS_PROJECT = "Which project is it for, dear?"
NEEDS_REF = "Paste the reference of the grant you issued before you mark it fulfilled."
BAD_PAGE = "That page has gone stale, dear. Open it again."


class Part(NamedTuple):
    """One part of a hardware order, as the person typed it: a ContentFile (already sanitised) or None for the screenshot."""
    name: str
    url: str
    price: object           # Decimal
    screenshot: object = None


# reads the pages use

def gettable(slug):
    """The base grant with this slug, active: an upgrade is never sold alone, so one gets None. Upgrades come along as `live_upgrades`."""
    item = ShopItem.objects.filter(slug=slug, active=True, base_item__isnull=True).first()
    if item is not None:
        item.live_upgrades = list(item.upgrades.filter(active=True))
    return item


def held(user, item_id):
    """How many of this base grant the person has in orders that are not rejected, refunded or cancelled."""
    total = OrderLine.objects.filter(order__user=user, order__status__in=rules.LIVE, item_id=item_id, upgrade=False).aggregate(total=Sum("quantity"))["total"]
    return total or 0


def project_problem(user, project, item):
    """Why this project may not have this grant, or "" (rules.hardware_problem over the facts in the database)."""
    design = project.submissions.filter(stage=submission_rules.DESIGN).first()
    return rules.hardware_problem(
        hardware=project.category.kind == Category.Kind.HARDWARE, owner_matches=project.user_id == user.pk,
        design_approved=bool(design and design.status == submission_rules.APPROVED), design_claimed=bool(design and design.claimed_at),
        project_status=project.status, held_by_project=Order.objects.filter(project=project, item=item, status__in=rules.LIVE).exists())


def eligible_projects(user, item):
    """The person's own hardware projects that may have this grant now: a design approved and collected, at the build, none yet."""
    mine = Project.objects.filter(user=user, category__kind=Category.Kind.HARDWARE, status=project_rules.BUILDING).select_related("category")
    return [project for project in mine if not project_problem(user, project, item)]


# placing an order

def refuse(problem):
    if problem:
        raise ValidationError(problem)


def line_of(item, quantity, upgrade=False):
    return rules.Line(item.pk, quantity, item.effective_cookies, item.usd_value, upgrade)


def locked_items(item_id):
    """The base grant (active, never an upgrade) and its active upgrades, rows locked, by id. (None, {}) when the grant is gone."""
    rows = list(ShopItem.objects.select_for_update().filter(Q(pk=item_id) | Q(base_item_id=item_id), active=True).order_by("pk"))
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


def hardware_upgrades(base, upgrades, parts_total):
    """The upgrades a hardware order adds on its own: as many of the best-value one as the parts need. Hardware buyers never pick them."""
    best = rules.best_upgrade([(u.pk, u.effective_cookies, u.usd_value) for u in upgrades.values()])
    needed = rules.upgrades_needed(base.usd_value, upgrades[best[0]].usd_value, parts_total) if best else 0
    return [(upgrades[best[0]], needed)] if needed else []


def hardware_parts(parts, maximum):
    """The parts, each one checked like its model would, and their total in dollars."""
    refuse(rules.parts_count_problem(len(parts), maximum))
    for part in parts:
        refuse(rules.price_problem(part.price))
        OrderPart(name=part.name, url=part.url, price=part.price).full_clean(exclude=["order", "screenshot"])
    return rules.parts_total([part.price for part in parts])


def save_lines(order, offer):
    for line in offer.lines:
        OrderLine.objects.create(order=order, item_id=line.item_id, quantity=line.quantity, unit_cookies=line.unit_cookies, unit_value=line.unit_value, upgrade=line.upgrade)


def save_parts(order, parts):
    for part in parts:
        OrderPart.objects.create(order=order, name=part.name, url=part.url, price=part.price, screenshot=part.screenshot or "")


def take_stock(offer):
    """Take what was ordered from the shelves that count their stock (an empty stock is unlimited and stays so)."""
    for line in offer.lines:
        ShopItem.objects.filter(pk=line.item_id, stock__isnull=False).update(stock=F("stock") - line.quantity)


@transaction.atomic
def place_order(user, item_id, *, nonce, quantity=1, upgrades=None, project_id=None, product_url="", user_note="", cart_screenshot=None, parts=(), max_parts=10):
    """Place an order for the grant `item_id` (a base item) and take the cookies, or raise ValidationError with a sentence for the person.

    Everything is checked here again under locks, whatever the form showed. `nonce` is the page's: a second post of it returns the first
    order. A hardware grant (needs_project) is for one of the person's own eligible projects, takes the listed `parts`, one of the item,
    and adds the upgrades the parts need by itself (`upgrades` is ignored). Any other grant takes a quantity and the upgrades asked for.
    `cart_screenshot` and each part's screenshot are ContentFiles already sanitised by submissions/images.py."""
    refuse(None if rules.NONCE.fullmatch(nonce or "") else BAD_PAGE)
    project_services.lock_person(user)
    placed = Order.objects.filter(user=user, nonce=nonce).first()
    if placed:
        return placed
    base, upgrade_items = locked_items(item_id)
    refuse(None if base else GONE)
    project, parts_total = None, None
    proves = base.kind == ShopItem.Kind.GRANT and not base.needs_project       # a plain grant shows its link and its cart; a hardware one its parts
    if base.needs_project:
        project = Project.objects.select_related("category").filter(pk=project_id).first()
        refuse(NEEDS_PROJECT if project is None else project_problem(user, project, base))
        parts_total, quantity = hardware_parts(list(parts), max_parts), 1
        counts = hardware_upgrades(base, upgrade_items, parts_total)
    else:
        parts = ()
        counts = chosen_upgrades(base, upgrade_items, upgrades or {})
        refuse(NEEDS_PROOF if proves and not (product_url and cart_screenshot) else "")
        refuse(rules.url_problem(product_url) if proves else "")
    refuse(rules.limit_problem(base.stackable, base.max_per_user, held(user, base.pk), quantity) or rules.stock_problem(base.stock, quantity))
    for upgrade, count in counts:
        refuse(rules.upgrade_count_problem(count, upgrade.max_per_user, upgrade.name) or rules.stock_problem(upgrade.stock, count))
    offer = rules.price([line_of(base, quantity)] + [line_of(up, count, upgrade=True) for up, count in counts])
    refuse(rules.parts_problem(parts_total, offer.value) if parts_total is not None else "")
    refuse(rules.afford_problem(ledger.balance(user), offer.cookies))
    order = Order(user=user, item=base, project=project, nonce=nonce, total_cookies=offer.cookies, total_value=offer.value,
                  product_url=product_url.strip() if proves else "", user_note=user_note, cart_screenshot=(cart_screenshot or "") if base.kind == ShopItem.Kind.GRANT else "")
    order.full_clean(exclude=["cart_screenshot"])
    order.save()
    save_lines(order, offer)
    save_parts(order, parts)
    ledger.debit(user, offer.cookies, reason=f"Grant: {base.name} (order {order.pk})"[:200], key=f"order:{order.pk}")
    take_stock(offer)
    return order


# changing an order: staff approve, reject, fulfil and refund; a person takes back one nobody has looked at

def give_back(order):
    """Cookies and stock go back to where they came from. Called once, when an order moves into a status that gives back."""
    ledger.credit(order.user, order.total_cookies, reason=f"Refund: {order.item.name} (order {order.pk})"[:200], key=f"order:{order.pk}:refund", kind=ledger_rules.REFUND)
    for line in order.lines.all():
        ShopItem.objects.filter(pk=line.item_id, stock__isnull=False).update(stock=F("stock") + line.quantity)


@transaction.atomic
def move(order_id, to, *, by=None, grant_ref=None, owner=None):
    """Move an order to a new status, once and only forward (rules.TRANSITIONS). Into rejected, cancelled or refunded the cookies and the
    stock go back (exactly once: the move happens once and the ledger refuses the refund key twice). Fulfilled needs the grant reference.
    `owner` restricts it to that person's own order. ValidationError with a sentence when it cannot be done, None when there is no such
    order (or it is not the owner's). Moving to the status it already has changes nothing."""
    found = Order.objects.select_related("user").filter(pk=order_id, **({"user": owner} if owner else {})).first()
    if found is None:
        return None
    project_services.lock_person(found.user)
    order = Order.objects.select_for_update().select_related("user", "item").get(pk=order_id)
    if order.status == to:
        return order
    refuse(None if rules.can_move(order.status, to) else f"An order that is {rules.LABELS[order.status].lower()} can't become {rules.LABELS[to].lower()}.")
    if grant_ref is not None:
        order.grant_ref = grant_ref.strip()
    refuse(NEEDS_REF if to == rules.FULFILLED and not order.grant_ref else "")
    if to in rules.GIVES_BACK:
        give_back(order)
    order.status = to
    if by is not None:
        order.reviewed_by, order.reviewed_at = by, timezone.now()
    order.save(update_fields=["status", "grant_ref", "reviewed_by", "reviewed_at"])
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
    which goes through move() so a rejection refunds. Only those fields are written, so a stale form cannot touch anything else."""
    stored = Order.objects.get(pk=order.pk)
    if order.status != stored.status:
        move(order.pk, order.status, by=by, grant_ref=order.grant_ref)
    current = Order.objects.select_for_update().get(pk=order.pk)
    current.public_note, current.internal_note, current.grant_ref = order.public_note, order.internal_note, order.grant_ref.strip()
    current.save(update_fields=["public_note", "internal_note", "grant_ref"])
    return current
