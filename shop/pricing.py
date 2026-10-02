"""Cookie prices. Pure Python, no Django, so it can be tested and reused anywhere.

    raw   = usd x cookies_per_usd x markup
    price = raw x (1 + jitter), then rounded UP to a step that grows with the size of the price

The jitter is a fraction between 0 and 4 percent taken from an HMAC of (item slug, region code) under a secret key, so
every item and region lands a little differently and the pattern cannot be rebuilt from the repo alone. The price is
deterministic, never below raw, and always a multiple of its step. Dollars stay with the callers: nothing here prints
or logs them (docs/security.md).
"""
import hashlib
import hmac
import math
from decimal import Decimal

ITEM_PRICE = "base"          # the "region" an item's own price is keyed with (real region codes are capital letters only)
MAX_JITTER = Decimal("0.04")
STEPS = ((50, 5), (200, 10), (1000, 25), (5000, 50))      # (below this many cookies, round up to a multiple of this)
LAST_STEP = 100


def raw_cookies(usd, cookies_per_usd, markup):
    return Decimal(usd) * Decimal(cookies_per_usd) * Decimal(markup)


def jitter(secret, slug, region_code):
    """A fraction between 0 and MAX_JITTER (both allowed), fixed for this item in this region. secret is bytes."""
    digest = hmac.new(secret, f"{slug}|{region_code}".encode(), hashlib.sha256).digest()
    return MAX_JITTER * int.from_bytes(digest[:8], "big") / (2**64 - 1)


def step_for(cookies):
    return next((step for below, step in STEPS if cookies < below), LAST_STEP)


def cookie_price(usd, cookies_per_usd, markup, secret, slug, region_code):
    """The whole cookie price of one unit, as an int."""
    wanted = raw_cookies(usd, cookies_per_usd, markup) * (1 + jitter(secret, slug, region_code))
    step = step_for(wanted)
    return math.ceil(wanted / step) * step
