"""Which signed in people used the site on which day (docs/metrics.md). Called by accounts/access.py for everybody let in to a participant page.
One ActiveDay row per person per day, never more than one write per person per minute per process. Stores no address, no browser and no page."""
import logging

from django.conf import settings
from django.core.cache import caches
from django.utils import timezone

from metrics.clock import site_day
from metrics.models import ActiveDay

log = logging.getLogger(__name__)
THROTTLE_SECONDS = 60


def touch(user):
    """Record that `user` was seen now. Never raises: counting must not break a page."""
    if not settings.METRICS_ENABLED:
        return
    if not caches["default"].add(f"seen:{user.pk}", 1, THROTTLE_SECONDS):
        return
    try:
        record(user.pk)
    except Exception:
        log.warning("activity could not be recorded")


def record(user_id):
    """Move today's last_seen forward, or make today's row (two workers racing end as one row: the unique constraint and ignore_conflicts)."""
    day, now = site_day(), timezone.now()
    if not ActiveDay.objects.filter(user_id=user_id, day=day).update(last_seen=now):
        ActiveDay.objects.bulk_create([ActiveDay(user_id=user_id, day=day, last_seen=now)], ignore_conflicts=True)
