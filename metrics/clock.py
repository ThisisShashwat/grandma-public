"""The one definition of "a day" for the metrics: the site's own zone (settings.TIME_ZONE), never the zone a request has activated for its person
(the dashboard shows each person their own zone), so a person's visit and a staff member's report always agree on where a day starts and ends."""
from zoneinfo import ZoneInfo

from django.conf import settings
from django.utils import timezone


def site_zone():
    return ZoneInfo(settings.TIME_ZONE)


def site_day(moment=None):
    """The calendar day of `moment` (now by default) in the site's zone."""
    return timezone.localtime(moment or timezone.now(), site_zone()).date()
