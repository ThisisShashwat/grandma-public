"""Grandma's demands as the guides' demands page and the home page's fridge show them (docs/projects.md "The demand pool").

The database is the one source: the active rows of the Demand table, in the order they were made (the seed order), each with the names of the active
categories it can be dealt for. Staff edit them in the admin. The same frozen records go to the page and to the fridge's JSON, never a model. The Python
lists in program/content only started the table (migration 0003) and are the fallback below.

The pick is kept in memory for POOL_SECONDS per process, the same pattern as shop/peek.py, so the home page and the guides do not read the table on every
view. A save or delete of a Demand or a Category, or a change of a demand's categories, clears it at once in that process; another gunicorn worker sees
the change within those seconds. LIVE_CACHE_SECONDS = 0 turns it off with the settings cache (the tests). A failed read never reaches the page: the last
pick is used, and on a process that never read, the frozen Python lists.
"""
import logging
import time
from functools import cache
from typing import NamedTuple

from django.conf import settings
from django.db.models import Prefetch
from django.db.models.signals import m2m_changed, post_delete, post_save
from django.dispatch import receiver

from program.content.demand_rules import RULES
from program.content.demands import POOL

from .models import Category, Demand

log = logging.getLogger(__name__)
POOL_SECONDS = 60          # how long a pick is kept
RETRY_SECONDS = 5          # after a failed read, how long the last pick (or the Python lists) is used before the database is tried again
_cache = None              # (expires at, demands), one per process; a save sets the time to 0 and keeps the demands as the last known pick


class PoolDemand(NamedTuple):
    name: str
    line: str          # what Grandma says
    tier: int          # 1 mild, 2 medium, 3 spicy
    plain: str         # the rule without her voice
    categories: tuple  # the names of the active categories it can be dealt for, in category order
    anything: bool     # it fits every active category, Other included

    @property
    def note(self):
        """What the fridge's script reads for each demand: [name, line, tier]."""
        return [self.name, self.line, self.tier]


@cache
def frozen():
    """The starting data as the Python lists have it: used only when the database cannot be read and nothing was ever read."""
    return tuple(PoolDemand(d.name, d.line, d.tier, RULES[d.name].plain, RULES[d.name].fits, RULES[d.name].anything) for d in POOL)


def record(demand, everywhere):
    names = tuple(category.name for category in demand.categories.all())
    return PoolDemand(demand.name, demand.grandma_line, demand.tier, demand.rule, names, bool(names) and set(names) == everywhere)


def read():
    """The active demands in the order they were made, with their active categories: three queries however many demands there are."""
    everywhere = set(Category.objects.filter(active=True).values_list("name", flat=True))
    demands = Demand.objects.filter(active=True).order_by("id").prefetch_related(Prefetch("categories", queryset=Category.objects.filter(active=True)))
    return tuple(record(demand, everywhere) for demand in demands)


def pick():
    """The pool: see `read`, kept for POOL_SECONDS. When the database cannot be read the last pick is used (the Python lists on a process that never had
    one) and it is tried again after RETRY_SECONDS, not on every view. With the cache off a failure is not hidden."""
    global _cache
    if not settings.LIVE_CACHE_SECONDS:
        return read()
    now = time.monotonic()
    if _cache and _cache[0] > now:
        return _cache[1]
    try:
        demands, seconds = read(), POOL_SECONDS
    except Exception:
        log.warning("the demands could not be read, using the last known ones")
        demands, seconds = _cache[1] if _cache else frozen(), RETRY_SECONDS
    _cache = (now + seconds, demands)
    return demands


@receiver([post_save, post_delete], sender=Demand)
@receiver([post_save, post_delete], sender=Category)
@receiver(m2m_changed, sender=Demand.categories.through)
def forget(**_):
    global _cache
    if _cache:
        _cache = (0, _cache[1])
