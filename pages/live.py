"""The one way code reads the settings staff edit in the admin (program/runtime.py, django-constance)."""
import logging
import time
from types import SimpleNamespace

from constance.signals import config_updated
from constance.utils import get_values
from django.conf import settings
from django.dispatch import receiver


log = logging.getLogger(__name__)
RETRY_SECONDS = 5          # after a failed read, how long the old answer is used before the database is tried again
_cache = None      # (expires at, settings), one per process


def live():
    """Every admin-editable setting as attributes, in a single query: live().DEAL_SIZE. Anything nobody has saved is its
    default, so this works on a fresh database too. (constance's own `config.X` makes one query per read and writes
    the default back on the first read, which a page view should not do.)
    The answer is kept for LIVE_CACHE_SECONDS (15) so a page that only needs the settings, like the home page, makes no
    query at all. A save in the admin clears it at once in that process; another gunicorn worker sees the change
    within those seconds. The returned object is shared: read it, never change it.
    A slow or unreachable database never takes a page down (owner, 2026-10-07: the public pages must not depend on it): when the read fails, the last
    answer is used (or the defaults on a process that never had one) and the database is tried again after RETRY_SECONDS, not on every request."""
    global _cache
    seconds = settings.LIVE_CACHE_SECONDS
    if seconds and _cache and _cache[0] > time.monotonic():
        return _cache[1]
    try:
        values = SimpleNamespace(**get_values())
    except Exception:
        if not seconds:
            raise
        log.warning("admin settings could not be read, using the last known ones")
        values = _cache[1] if _cache else SimpleNamespace(**{key: row[0] for key, row in settings.CONSTANCE_CONFIG.items()})
        _cache = (time.monotonic() + RETRY_SECONDS, values)
        return values
    if seconds:
        _cache = (time.monotonic() + seconds, values)
    return values


@receiver(config_updated)
def forget(**_):
    global _cache
    _cache = None
