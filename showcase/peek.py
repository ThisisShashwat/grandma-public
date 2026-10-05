"""The Blue Ribbon wall peek for the home page (admin setting HOME_RIBBON_PEEK, docs/public-pages.md "The home page peek").

It hands out the same frozen `Card` records as /ribbons/, from the same query (showcase/public.py `wall_rows`), so the home page can show
exactly what the wall shows and nothing more. Wired into the home template by grandma/jinja.py; `pages` never imports `showcase`.
"""
from pages.live import live

from . import public


def pick(count):
    """The newest `count` projects on the wall. 0 means the peek is switched off: nothing is read, no query is made. An empty wall gives an empty tuple.
    The settings are read again here, but only while the peek is on (the wall's own rules depend on SHOW_REJECTED_PUBLICLY)."""
    return public.wall_peek(live(), count) if count else ()
