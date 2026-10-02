"""What every template can use: links, content, and the JSON handed to the browser."""
import re

from markupsafe import Markup, escape

from . import config, payout
from .content.demands import LEVELS, POOL, TIERS
from .content.faces import FACES

_urls = {key: url for row in config.FOOTER for key, _, url in row} | config.LINKS


def link(key):
    """URL for a named link, or "#" while it is still empty in config.py."""
    return _urls.get(key) or "#"


def link_attrs(key):
    """href plus new-tab attributes for real web links, ready to drop inside an <a ...>."""
    url = link(key)
    new_tab = ' target="_blank" rel="noopener"' if url.startswith("http") else ""
    return Markup(f'href="{escape(url)}"{new_tab}')


def _camel(name):
    return re.sub(r"_([a-z])", lambda m: m[1].upper(), name)


def site_data():
    """Everything the browser needs, as JSON. static/js/core/data.js reads it. Constants live in Python only."""
    return {
        "launch": config.LAUNCH,
        "freeAsks": config.FREE_ASKS,
        "tiers": TIERS,
        "levels": LEVELS,
        "pool": POOL,
        "faces": [{"name": f["name"], "say": f["say"]} for f in FACES],
        "pay": {_camel(key): value for key, value in payout.CONFIG.items()},
    }


def context():
    return {
        "site": config.SITE, "footer": config.FOOTER, "link": link, "link_attrs": link_attrs,
        "site_data": site_data(), "pool": POOL, "tiers": TIERS, "levels": LEVELS, "faces": FACES,
        "free_asks": config.FREE_ASKS,
    }
