"""How many times four public pages are opened per day (docs/metrics.md), only while the COUNT_VISITS admin setting is on. A middleware that looks at the
finished response: it never touches request.user, the session or a cookie (the public pages read no session), and it makes no database query while
a request is served. Views are added up in this process's memory and written to DayViews at most every FLUSH_SECONDS, by the request that finds the
flush due; a restart loses at most that many seconds of counts, and a failed write drops them. The User-Agent is read only to skip robots and is never
kept, and nothing about the address, the browser or who asked is stored: the table holds a number per day and page."""
import logging
import re
import threading
import time
from collections import Counter

from django.conf import settings
from django.db.models import F

from metrics.clock import site_day
from metrics.models import DayViews
from pages.live import live

log = logging.getLogger(__name__)
FLUSH_SECONDS = 30
BOTS = re.compile(r"bot|crawl|spider|slurp|curl|wget|python-requests|monitor|preview|headless|facebookexternalhit", re.I)

PAGES = {("/", 200): "home", ("/shop/", 200): "shop", ("/login/hackclub/", 302): "signin"}          # (path, status) -> page; the guides are any path under /guides/

lock = threading.Lock()
buffer = Counter()          # (day, page) -> views not yet written
last_flush = time.monotonic()


def page_of(path, status):
    """The page name a finished response counts as, or None. Sign in is counted where it really starts (/login/ redirects there)."""
    if path.startswith("/guides/") and status == 200:
        return "guides"
    return PAGES.get((path, status))


def counted(request, response):
    """The page this exchange counts as, or None for a method that only looks, a page nobody counts or a robot."""
    page = page_of(request.path_info, response.status_code) if request.method == "GET" else None
    return None if page and BOTS.search(request.META.get("HTTP_USER_AGENT", "")) else page


def add(page):
    with lock:
        buffer[(site_day(), page)] += 1


def flush_due():
    global last_flush
    with lock:
        if time.monotonic() - last_flush < FLUSH_SECONDS:
            return False
        last_flush = time.monotonic()
        return True


def flush():
    """Write the buffered counts to DayViews, adding to what is there. A failure drops them."""
    with lock:
        taken = Counter(buffer)
        buffer.clear()
    try:
        for (day, page), views in taken.items():
            save(day, page, views)
    except Exception:
        log.warning("visit counts could not be saved")


def save(day, page, views):
    """Add `views` to the day's row, making it if there is none (a worker that made it first is not lost: the add is done again)."""
    if DayViews.objects.filter(day=day, page=page).update(views=F("views") + views):
        return
    _, created = DayViews.objects.get_or_create(day=day, page=page, defaults={"views": views})
    if not created:
        DayViews.objects.filter(day=day, page=page).update(views=F("views") + views)


def count_visits(get_response):
    def middleware(request):
        response = get_response(request)
        page = counted(request, response) if settings.METRICS_ENABLED else None
        if page and live().COUNT_VISITS:
            add(page)
            if flush_due():
                flush()
        return response
    return middleware
