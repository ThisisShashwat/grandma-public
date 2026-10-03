"""The rules of getting a grant, as plain functions: statuses and which moves are allowed, what an order costs, how many upgrades
cover a list of parts, who may have how many, stock, who may buy a hardware grant and for which project, and what is wrong with a
link, a part or a price. No Django import and no database: the decisions are made here and orders/services.py only applies them.
Every problem is a sentence in Grandma's voice, or "" when there is none. Why each rule exists: docs/orders.md."""
import math
import re
from decimal import Decimal
from typing import NamedTuple

from submissions import links

PENDING, APPROVED, FULFILLED, REJECTED, REFUNDED, CANCELLED = "pending", "approved", "fulfilled", "rejected", "refunded", "cancelled"
STATUSES = ((PENDING, "Waiting for Grandma"), (APPROVED, "Approved"), (FULFILLED, "Paid"), (REJECTED, "Turned down"),
            (REFUNDED, "Refunded"), (CANCELLED, "Taken back"))
LABELS = dict(STATUSES)

LIVE = (PENDING, APPROVED, FULFILLED)               # these count toward a person's limit and take from the stock
GIVES_BACK = (REJECTED, REFUNDED, CANCELLED)        # moving an order here puts its cookies and its stock back, once
TRANSITIONS = {PENDING: (APPROVED, REJECTED, CANCELLED), APPROVED: (FULFILLED, REJECTED), FULFILLED: (REFUNDED,)}

MAX_PRICE = Decimal("99999.99")                     # what one part may cost, in dollars: a typo guard
NONCE = re.compile(r"[0-9a-f]{32}")                 # what a page puts in its hidden field: a uuid4 in hex
MAX_QUANTITY = 100                                  # no stackable item is bought more than this many at once, whatever its limit says


def can_move(current, to):
    return to in TRANSITIONS.get(current, ())


class Line(NamedTuple):
    """One line of an order, frozen from the database at the moment of ordering: the base grant, then one per upgrade item."""
    item_id: int
    quantity: int
    unit_cookies: int
    unit_value: Decimal
    upgrade: bool


class Offer(NamedTuple):
    lines: tuple
    cookies: int                # what the person pays, in cookies
    value: Decimal              # what the grant is worth in dollars, upgrades included


def price(lines):
    """What a list of lines costs and is worth."""
    return Offer(tuple(lines), sum(line.quantity * line.unit_cookies for line in lines), sum(line.quantity * line.unit_value for line in lines))


def upgrades_needed(base_value, upgrade_value, parts_total):
    """How many upgrades of `upgrade_value` dollars make a grant of `base_value` cover `parts_total` dollars of parts. 0 when the
    base already does."""
    if upgrade_value <= 0:
        raise ValueError("An upgrade is worth something.")
    return 0 if parts_total <= base_value else math.ceil((parts_total - base_value) / upgrade_value)


def best_upgrade(options):
    """Of several upgrades, the one hardware orders add: the best deal for the buyer (fewest cookies per dollar), the smaller step
    on a tie so there is less left over. `options` are (item_id, unit_cookies, unit_value); None if there are none."""
    return min(options, key=lambda o: (Decimal(o[1]) / o[2], o[2]), default=None)


def limit_problem(stackable, max_per_user, held, wanted):
    """Why this person may not have `wanted` more of an item they hold `held` of (in orders that are not rejected, refunded or
    cancelled). A non-stackable item is one per person; a stackable one up to max_per_user, or without end when that is empty."""
    cap = (max_per_user if stackable else 1)
    if wanted < 1 or wanted > MAX_QUANTITY:
        return f"Between one and {MAX_QUANTITY}, dear."
    if cap is None or held + wanted <= cap:
        return ""
    if not stackable:
        return "You've already got one of those, dear. One per person."
    left = max(cap - held, 0)
    return f"You may have {cap} of those and you hold {held} already, dear." + (f" {left} more at the very most." if left else "")


def stock_problem(stock, wanted):
    """None means unlimited."""
    if stock is None or stock >= wanted:
        return ""
    return "That's all gone, dear." if stock == 0 else f"Only {stock} left, dear."


def upgrade_count_problem(count, max_per_user, name):
    """Upgrades are counted per order: up to the upgrade's own limit, or without end when it has none."""
    if count < 0:
        return "Not a negative number, dear."
    if max_per_user is not None and count > max_per_user:
        return f"{name}: {max_per_user} at the very most, dear."
    return ""


def upgrade_problem(base_id, upgrade_base_id):
    """An upgrade is only ever bought with the base it belongs to."""
    return "" if base_id is not None and upgrade_base_id == base_id else "That upgrade doesn't go with that grant, dear."


def afford_problem(balance, cookies):
    if balance >= cookies:
        return ""
    if balance <= 0:
        return f"That's {cookies:,} cookies, dear, and you have none. I don't do credit."
    return f"That's {cookies:,} cookies, dear, and you have {balance:,}. I don't do credit."


def hardware_problem(*, hardware, owner_matches, design_approved, design_claimed, project_status, held_by_project):
    """Whether a hardware project may have a grant: it is the person's own, a hardware project, its design ship was approved AND
    the person has heard it from Grandma, they are waiting for parts (project status `awaiting_build`), and the project has no grant already
    (rejected, refunded and cancelled ones do not count). The build may be shipped here, elsewhere or not at all: nothing waits for it."""
    if not owner_matches:
        return "That isn't your project, dear."
    if not hardware:
        return "That one isn't a hardware project, dear. These grants are for things you build."
    if not design_approved or not design_claimed:
        return "I haven't approved a design for that one yet, dear. Ship the design first."
    if project_status != "awaiting_build":
        return "That project isn't waiting for parts, dear."
    if held_by_project:
        return "That project already has a grant on the way, dear. One each."
    return ""


def url_problem(url):
    """A link to a product: http or https, a real domain, no user name or password (the same rules as the links people hand in)."""
    return links.web_url_problem(url.strip())


def price_problem(value):
    """What one part costs, in dollars: more than nothing, no more than MAX_PRICE, whole cents."""
    if value is None or not value.is_finite():
        return "A price in dollars, dear."
    if value <= 0:
        return "A part costs something, dear."
    if value > MAX_PRICE:
        return f"Not more than ${MAX_PRICE:,}, dear."
    if value != value.quantize(Decimal("0.01")):
        return "Dollars and cents, dear. Two decimals at the most."
    return ""


def parts_total(prices):
    return sum(prices, Decimal("0"))


def parts_problem(total, value):
    """The parts may not come to more than the grant is worth."""
    if total > value:
        return f"Those parts come to ${total:,.2f} and the grant is worth ${value:,.2f}, dear."
    return ""


def parts_count_problem(count, maximum):
    if count < 1:
        return "Every part you are buying, dear. I need at least one."
    if count > maximum:
        return f"{maximum} parts at the very most, dear."
    return ""
