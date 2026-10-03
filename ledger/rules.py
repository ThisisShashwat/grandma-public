"""The cookie ledger's rules as plain functions. No Django import, no database: the maths is decided here and the
service layer (services.py) only applies it. Cookie amounts are whole numbers, never fractions."""

EARNING, SPENDING, REFUND, ADJUSTMENT = "earning", "spending", "refund", "adjustment"
KINDS = ((EARNING, "Earning"), (SPENDING, "Spending"), (REFUND, "Refund"), (ADJUSTMENT, "Adjustment"))
GAINS = (EARNING, REFUND)             # always a positive amount; spending is always negative; an adjustment is either


class InsufficientCookies(Exception):
    """The change would take the balance below zero."""


def sign_fits(kind, amount):
    """Does this signed amount make sense for this kind of entry?"""
    if kind in GAINS:
        return amount > 0
    if kind == SPENDING:
        return amount < 0
    return kind == ADJUSTMENT and amount != 0


def check(kind, amount, reason, key):
    """Raise ValueError for an entry that must never be written."""
    if type(amount) is not int:
        raise ValueError("Cookie amounts are whole numbers.")
    if not sign_fits(kind, amount):
        raise ValueError(f"A {kind} entry cannot be {amount} cookies.")
    if not reason.strip() or not key.strip():
        raise ValueError("Every entry needs a reason and an idempotency key.")


def overdraws(balance, change):
    """True when adding `change` (negative to spend) to `balance` would leave less than nothing."""
    return balance + change < 0
