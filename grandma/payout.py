"""Grandma's payout maths: pure functions, no Flask, so the shop, a dashboard or a backend can import it.

The formula comes from the "Modifiers ysws" canvas PDF and is FROZEN. Do not change a constant or the shape of it
without the owner saying so (docs/payout.md has the reference table that tests/test_payout.py checks).

    x          = min(xmax, demand tiers + cool + huge (at 20 hours and up) + Blue Ribbon)
    multiplier = 1 + (cap - 1) * (1 - e^(-k x)) / (1 - e^(-k xmax))
    cookies    = base * multiplier * cookies_per_usd * hours

Dollars are internal only. Never show a dollar figure or a per-hour rate anywhere on the site.
static/js/modules/pay/math.js is the browser twin of this file and reads the same CONFIG.
"""
from math import exp

CONFIG = {
    "base": 3.25,              # base rate per hour in USD, internal only
    "cap": 1.85,               # multiplier at x = xmax
    "k": -0.8,                 # negative = back-loaded: most projects sit low, stacked ones climb
    "xmax": 1.3,               # 3 x 0.3 (demands) + 0.2 + 0.1 + 0.1 (bonuses): the biggest x anyone can reach
    "tier": {1: 0.1, 2: 0.2, 3: 0.3},   # x per demand
    "quality": 0.2,            # "Grandma loved it" (cool, high quality project)
    "huge": 0.1,               # huge project ...
    "huge_hours": 20,          # ... at this many hours and above
    "ribbon": 0.1,             # Blue Ribbon
    "cookies_per_usd": 10,

    # Grandma's face: look only, never changes a payout. Score = demands and hours, each as a share of its maximum.
    "hours_max": 60,           # the hours slider's maximum
    "demand_weight": 0.6,
    "hours_weight": 0.4,
    "face_at": [0.15, 0.25, 0.35, 0.47, 0.58, 0.70, 0.82, 0.94],   # score needed for faces 2 to 9
}


def multiplier(x):
    c = CONFIG
    return 1 + (c["cap"] - 1) * (1 - exp(-c["k"] * x)) / (1 - exp(-c["k"] * c["xmax"]))


def x_for(tiers=(), hours=0, quality=False, ribbon=False):
    """tiers: up to three demand tiers (0 means an empty slot)."""
    c = CONFIG
    demands = sum(c["tier"].get(t, 0) for t in tiers)
    return min(c["xmax"], demands + (c["quality"] if quality else 0)
               + (c["huge"] if hours >= c["huge_hours"] else 0) + (c["ribbon"] if ribbon else 0))


def usd_per_hour(x):
    """Internal only: exists so the PDF table can be checked. Never show it."""
    return CONFIG["base"] * multiplier(x)


def cookies(tiers=(), hours=0, quality=False, ribbon=False):
    """Cookies for the whole project, not rounded: round when you show it."""
    return usd_per_hour(x_for(tiers, hours, quality, ribbon)) * CONFIG["cookies_per_usd"] * hours


def face(tiers=(), hours=0, quality=False, ribbon=False, hours_max=None):
    """Which Grandma, 0 to 9 (index into content.faces.FACES). Furious only while no demand is picked."""
    c = CONFIG
    if not any(tiers):
        return 0
    hours_max = hours_max or c["hours_max"]
    score = (c["demand_weight"] * x_for(tiers, hours, quality, ribbon) / c["xmax"]
             + c["hours_weight"] * min(1, max(0, (hours - 1) / (hours_max - 1))))
    f = 1
    for i, t in enumerate(c["face_at"]):
        if score >= t:
            f = i + 2
    return f
