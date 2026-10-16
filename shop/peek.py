"""The Pantry items for the home page (admin setting HOME_PANTRY_PEEK, docs/shop.md "The home page peek").

Every active item ticked "Show on the home page" is in it, in Pantry order, with no limit: a by hand item, a sold out item and a ribbon only item are all there
(the shop's own cards say which). The home page is public, so this always reads the shop as a visitor sees it: a ribbon only item is locked, even when the
viewer holds a Blue Ribbon. It hands out the same frozen Product records as the Pantry, never a model.

The pick is kept in memory for PEEK_SECONDS per process, the same pattern as pages/live.py, so a crowd or a crawler on the home page does not read the shop
on every view (nothing caches the HTML itself). A save or delete of a ShopItem clears it at once in that process; another gunicorn worker sees the change
within those seconds. LIVE_CACHE_SECONDS = 0 turns it off with the settings cache (the tests). A failed read never reaches the page.
"""
import logging
import time

from django.conf import settings
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from . import catalog
from .models import ShopItem

log = logging.getLogger(__name__)
PEEK_SECONDS = 60          # how long a pick is kept
RETRY_SECONDS = 5          # after a failed read, how long the last pick (or nothing) is used before the database is tried again
_cache = None              # (expires at, picks), one per process


def read():
    """The products of the Pantry in shop order (shelf by shelf) that are ticked "Show on the home page" in the admin. The tick is not in the public Product
    record (that list is pinned): it is read as a set of slugs beside it, in the same cached read."""
    ticked = set(ShopItem.objects.filter(show_on_home=True).values_list("slug", flat=True))
    shelved = (product for shelf in catalog.build(ribbon=False).shelves for product in shelf.products)
    return tuple(p for p in shelved if p.slug in ticked)


def pick():
    """The peek's products: see `read`, kept for PEEK_SECONDS. An empty shop gives an empty tuple, and that is kept too. When the database cannot be read the
    last pick is used (nothing on a process that never had one) and it is tried again after RETRY_SECONDS, not on every view. The switch (HOME_PANTRY_PEEK)
    is the caller's: the home page does not ask while it is off."""
    global _cache
    if not settings.LIVE_CACHE_SECONDS:
        return read()
    now = time.monotonic()
    if _cache and _cache[0] > now:
        return _cache[1]
    try:
        picks, seconds = read(), PEEK_SECONDS
    except Exception:
        log.warning("the Pantry peek could not be read, using the last known one")
        picks, seconds = _cache[1] if _cache else (), RETRY_SECONDS
    _cache = (now + seconds, picks)
    return picks


@receiver([post_save, post_delete], sender=ShopItem)
def forget(**_):
    global _cache
    _cache = None
