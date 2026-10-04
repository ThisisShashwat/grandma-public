"""Widgets: trusted markup that replaces an empty <div data-widget="name"></div> in a guide.

The swap happens AFTER the guide text was sanitized (guides/loader.py), so this markup never goes through the sanitizer and
a guide author cannot write any of it. One small function per widget, listed in WIDGETS. An unknown name renders nothing.
Each widget that needs JavaScript or CSS is named in the guide's front matter, and the page loads them only then.
"""
import re
from math import exp

from django.template.loader import render_to_string
from django.utils.html import format_html

from program import payout
from program.content.demand_rules import RULES
from program.content.demands import LEVELS, POOL, TIERS
from program.content.faces import FACES

PLACEHOLDER = re.compile(r'<div data-widget="([\w-]+)"[^>]*></div>')
CHANNEL = re.compile(r'<span data-slack="(grandma|help)"></span>')
CHANNELS = {"grandma": ("#grandma", "slack_grandma"), "help": ("#grandma-help", "slack_help")}     # name shown, key of the admin link


def payout_calculator():
    """The calculator from the home page. static/js/pages/guides.js mounts it."""
    return render_to_string("components/calculator.html", {"faces": FACES})


def demands_list():
    """All the demands with their plain rules, grouped by grumpiness level. Pure HTML, no JavaScript."""
    groups = [(LEVELS[tier], TIERS[tier], [(demand, RULES[demand.name]) for demand in POOL if demand.tier == tier]) for tier in LEVELS]
    return render_to_string("components/demands_list.html", {"groups": groups})


EXAMPLES = (
    ("one mild demand, 12 hours", dict(tiers=[1], hours=12)),
    ("one medium demand and Grandma loved it, 12 hours", dict(tiers=[2], hours=12, quality=True)),
    ("one mild demand, 60 hours", dict(tiers=[1], hours=60)),
    ("two medium demands, 20 hours", dict(tiers=[2, 2], hours=20)),
    ("three spicy demands, loved, Blue Ribbon, 20 hours", dict(tiers=[3, 3, 3], hours=20, quality=True, ribbon=True)),
    ("the same at 60 hours", dict(tiers=[3, 3, 3], hours=60, quality=True, ribbon=True)),
)


def _kept_description(tiers):
    names = {1: "mild", 2: "medium", 3: "spicy"}
    counts = {}
    for t in tiers:
        counts[t] = counts.get(t, 0) + 1
    num_words = {1: "One", 2: "Two", 3: "Three"}
    parts = [f"{num_words.get(c, str(c))} {names.get(t, 'unknown')} demand{'s' if c > 1 else ''}" for t, c in counts.items()]
    return ", ".join(parts) if parts else "No demand"


def _format_extras(kwargs):
    extras = []
    if kwargs.get("quality"):
        extras.append("Grandma loved it")
    if kwargs.get("ribbon"):
        extras.append("Blue Ribbon")
    if kwargs.get("hours", 0) >= payout.CONFIG["huge_hours"]:
        extras.append("Huge project")
    if kwargs.get("ribbon_holder"):
        extras.append("Ribbon holder")
    return ", ".join(extras) if extras else "None"


def reference_rows():
    rows = []
    for label, kwargs in EXAMPLES:
        rows.append({
            "label": label,
            "kept": _kept_description(kwargs.get("tiers", ())),
            "hours": kwargs.get("hours", 0),
            "extras": _format_extras(kwargs),
            "cookies": payout.shown(payout.cookies(**kwargs)),
        })
    return rows


def worked_example():
    """Intermediate numbers for the worked example (one mild demand, 12 hours)."""
    tiers = [1]
    hours = 12
    c = payout.CONFIG
    x = payout.x_for(tiers=tiers, hours=hours)
    mult = payout.multiplier(x)
    raw_cookies = payout.cookies(tiers=tiers, hours=hours)
    shown_cookies = payout.shown(raw_cookies)

    k = c["k"]
    xmax = c["xmax"]
    neg_k = -k
    exp_num_pow = neg_k * x
    exp_den_pow = neg_k * xmax
    exp_num = exp(exp_num_pow)
    exp_den = exp(exp_den_pow)
    term_num = 1 - exp_num
    term_den = 1 - exp_den
    ratio = term_num / term_den if term_den else 0

    base_cookies = c["base"] * c["cookies_per_usd"]
    base_display = int(base_cookies) if isinstance(base_cookies, float) and base_cookies.is_integer() else base_cookies

    return {
        "tiers": tiers,
        "hours": hours,
        "x": x,
        "cap": c["cap"],
        "cap_minus_1": round(c["cap"] - 1, 4),
        "k": k,
        "neg_k": round(neg_k, 4),
        "xmax": xmax,
        "exp_num_pow": round(exp_num_pow, 4),
        "exp_den_pow": round(exp_den_pow, 4),
        "exp_num": round(exp_num, 4),
        "exp_den": round(exp_den, 4),
        "term_num": round(term_num, 4),
        "term_den": round(term_den, 4),
        "ratio": round(ratio, 4),
        "multiplier": mult,
        "multiplier_4dp": f"{mult:.4f}",
        "base_cookies": base_display,
        "raw_cookies": raw_cookies,
        "raw_cookies_2dp": f"{raw_cookies:.2f}",
        "shown_cookies": shown_cookies,
    }


def cookie_formula():
    """The exact formula, constants, worked example, and reference table. Pure HTML, no JavaScript."""
    c = payout.CONFIG
    base_cookies = c["base"] * c["cookies_per_usd"]
    base_display = int(base_cookies) if isinstance(base_cookies, float) and base_cookies.is_integer() else base_cookies
    context = {
        "config": c,
        "base_cookies": base_display,
        "worked": worked_example(),
        "reference_rows": reference_rows(),
    }
    return render_to_string("components/cookie_formula.html", context)


WIDGETS = {
    "payout-calculator": payout_calculator,
    "demands-list": demands_list,
    "cookie-formula": cookie_formula,
}


def channel(which, links):
    """A Slack channel's name, as a link when the admin has set its address (a web address only) and as plain text while it is empty."""
    name, key = CHANNELS[which]
    url = links.get(key, "")
    if url.startswith("http"):
        return format_html('<a href="{}" target="_blank" rel="noopener noreferrer">{}</a>', url, name)
    return format_html('<b class="slack-name">{}</b>', name)


def expand(html, links=None):
    """Swap every widget placeholder for its widget, wrapped in a div the guide styles can find, and every
    <span data-slack="grandma"></span> or "help" for that channel's name (a link only when its address is set). `links` is the
    program's links by name (pages.context.program_links)."""
    html = PLACEHOLDER.sub(lambda m: f'<div class="widget widget--{m[1]}">{WIDGETS[m[1]]()}</div>' if m[1] in WIDGETS else "", html)
    return CHANNEL.sub(lambda m: channel(m[1], links or {}), html)
