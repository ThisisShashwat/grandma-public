"""The rules of getting a grant, as plain functions: statuses and which moves are allowed, what an order costs, who may have how many,
stock, and what is wrong with a link. No Django import and no database: the decisions are made here and orders/services.py only applies them.
Every problem is a sentence in Grandma's voice, or "" when there is none. Why each rule exists: docs/orders.md."""
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
    """Upgrades are counted per order: up to the upgrade's own limit, or MAX_QUANTITY (what a line of an order can hold) when it has none."""
    if count < 0:
        return "Not a negative number, dear."
    most = MAX_QUANTITY if max_per_user is None else min(max_per_user, MAX_QUANTITY)
    if count > most:
        return f"{name}: {most} at the very most, dear."
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


def url_problem(url):
    """A link to a product: http or https, a real domain, no user name or password (the same rules as the links people hand in)."""
    return links.web_url_problem(url.strip())
