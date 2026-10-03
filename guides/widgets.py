"""Widgets: trusted markup that replaces an empty <div data-widget="name"></div> in a guide.

The swap happens AFTER the guide text was sanitized (guides/loader.py), so this markup never goes through the sanitizer and
a guide author cannot write any of it. One small function per widget, listed in WIDGETS. An unknown name renders nothing.
Each widget that needs JavaScript or CSS is named in the guide's front matter, and the page loads them only then.
"""
import re

from django.template.loader import render_to_string
from django.utils.html import format_html

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


WIDGETS = {"payout-calculator": payout_calculator, "demands-list": demands_list}


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
