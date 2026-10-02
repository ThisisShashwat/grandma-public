"""Cookie prices. Pure Python, no Django, so it can be tested and reused anywhere.

    raw   = usd x cookies_per_usd x markup
    price = raw rounded UP to a nice round number, the step growing with the size of the price

Never below raw, always a multiple of its step. The owner chose to make the rate visible (docs/decisions.md), so there is
no secret and no per-item wobble: the same dollars and rate class always give the same price.
"""
import math
from decimal import Decimal

STEPS = ((50, 5), (200, 10), (1000, 25), (5000, 50))      # (below this many cookies, round up to a multiple of this)
LAST_STEP = 100


def raw_cookies(usd, cookies_per_usd, markup):
    return Decimal(usd) * Decimal(cookies_per_usd) * Decimal(markup)


def step_for(cookies):
    return next((step for below, step in STEPS if cookies < below), LAST_STEP)


def cookie_price(usd, cookies_per_usd, markup):
    """The whole cookie price of one unit, as an int."""
    raw = raw_cookies(usd, cookies_per_usd, markup)
    step = step_for(raw)
    return math.ceil(raw / step) * step
