"""A few Pantry items for the home page (admin setting HOME_PANTRY_PEEK, docs/shop.md "The home page peek").

The home page is public, so this always reads the shop as a visitor sees it: never a ribbon only item, even when the viewer holds a Blue Ribbon.
It hands out the same frozen Product records as the Pantry, never a model.

The pick is kept in memory for PEEK_SECONDS per process, the same pattern as pages/live.py, so a crowd or a crawler on the home page does not read the shop
on every view (nothing caches the HTML itself). A save or delete of a ShopItem clears it at once in that process; another gunicorn worker sees the change
within those seconds. LIVE_CACHE_SECONDS = 0 turns it off with the settings cache (the tests). A failed read never reaches the page.
"""
import logging
import time
from itertools import islice

from django.conf import settings
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from . import catalog
from .models import ShopItem

log = logging.getLogger(__name__)
PEEK_SECONDS = 60          # how long a pick is kept
RETRY_SECONDS = 5          # after a failed read, how long the last pick (or nothing) is used before the database is tried again
_cache = {}                # count -> (expires at, picks), one per process


def read(count):
    """The first `count` products of the Pantry in shop order (shelf by shelf), skipping the by hand ones and the sold out ones, which a peek does not need."""
    shelved = (product for shelf in catalog.build(ribbon=False).shelves for product in shelf.products)
    return tuple(islice((p for p in shelved if p.available and not p.manual), count))


def pick(count):
    """The peek's products: see `read`, kept for PEEK_SECONDS. 0 means the peek is switched off: nothing is read, no query is made. An empty shop gives
    an empty tuple, and that is kept too. When the database cannot be read the last pick is used (nothing on a process that never had one) and it is tried
    again after RETRY_SECONDS, not on every view."""
    if not count:
        return ()
    if not settings.LIVE_CACHE_SECONDS:
        return read(count)
    now = time.monotonic()
    kept = _cache.get(count)
    if kept and kept[0] > now:
        return kept[1]
    try:
        picks, seconds = read(count), PEEK_SECONDS
    except Exception:
        log.warning("the Pantry peek could not be read, using the last known one")
        picks, seconds = kept[1] if kept else (), RETRY_SECONDS
    _cache[count] = (now + seconds, picks)
    return picks


@receiver([post_save, post_delete], sender=ShopItem)
def forget(**_):
    _cache.clear()
