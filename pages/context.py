"""What every template can use: links, content, and the JSON handed to the browser."""
import re
from functools import partial

from markupsafe import Markup, escape

from pages.live import live
from program import config, payout
from program.content.demands import LEVELS, TIERS
from program.content.faces import FACES

_footer_urls = {key: url for row in config.FOOTER for key, _, url in row}


def program_links(cfg):
    """The program's links from the admin settings (LINK_SIGNUP becomes "signup"), plus the footer's fixed ones."""
    return _footer_urls | {k.removeprefix("LINK_").lower(): v for k, v in vars(cfg).items() if k.startswith("LINK_")}


def link(urls, key):
    """URL for a named link, or "#" while it is still empty in the admin."""
    return urls.get(key) or "#"


def link_attrs(urls, key):
    """href plus new-tab attributes for real web links, ready to drop inside an <a ...>."""
    url = link(urls, key)
    new_tab = ' target="_blank" rel="noopener"' if url.startswith("http") else ""
    return Markup(f'href="{escape(url)}"{new_tab}')


def _camel(name):
    return re.sub(r"_([a-z])", lambda m: m[1].upper(), name)


def site_data(cfg):
    """Everything the browser needs, as JSON. static/js/core/data.js reads it. Constants live in Python only.
    The demands for the fridge are not here: they are in the database, and `pages` stays below the apps. The home page adds them
    (templates/pages/home.html, from projects/pool.py), the one page whose script reads them."""
    return {
        "launch": cfg.LAUNCH,
        "freeAsks": cfg.REDEALS_FREE,
        "tiers": TIERS,
        "levels": LEVELS,
        "faces": [{"name": f["name"], "say": f["say"]} for f in FACES],
        "pay": {_camel(key): value for key, value in payout.CONFIG.items()},
    }


def context(request):
    """Django context processor (settings.TEMPLATES, Jinja2 backend): the same names the Flask version injected."""
    cfg = live()
    urls = program_links(cfg)
    return {
        "site": config.SITE, "footer": config.FOOTER, "link": partial(link, urls), "link_attrs": partial(link_attrs, urls),
        "site_data": site_data(cfg), "tiers": TIERS, "levels": LEVELS, "faces": FACES,
        "free_asks": cfg.REDEALS_FREE,
        "home_pantry_peek": cfg.HOME_PANTRY_PEEK,                                  # the Pantry peek's switch: it shows every ticked item, so there is no count
        "home_ribbon_count": cfg.HOME_PEEK_COUNT if cfg.HOME_RIBBON_PEEK else 0,   # how many Blue Ribbon wall cards the home page shows, 0 = the switch is off
    }
