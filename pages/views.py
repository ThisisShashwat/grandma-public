import logging

from django.db import DatabaseError, connection
from django.http import HttpResponse
from django.shortcuts import render
from django.template.loader import render_to_string
from django.utils.cache import add_never_cache_headers
from django.views.decorators.http import require_safe

from program.content.errors import ERRORS

log = logging.getLogger(__name__)

LAST_RESORT = "<!doctype html><title>Something went wrong</title><p>Something went wrong, dear. Please go back and try again.</p>"


@require_safe
def healthz(request):
    """Is the process up? No database, no settings: a host's liveness probe."""
    return HttpResponse("ok", content_type="text/plain")


@require_safe
def readyz(request):
    """Can the process reach its database? 503 when not: a host's readiness probe."""
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
    except DatabaseError:
        return HttpResponse("database unreachable", status=503, content_type="text/plain")
    return HttpResponse("ok", content_type="text/plain")


@require_safe
def home(request):
    return render(request, "pages/home.html")


def error_page(request, key, plain=False):
    """Grandma's page for one entry of ERRORS, with that entry's status, never cached, nothing from the request in it. The page
    with the header and the footer reads the admin settings and the session user, so it is skipped for the 500 (`plain`: the database is
    often the very thing that broke) and for a request that died before the user was attached (a bad Host header, a static file).
    When it fails anyway it falls back to the standalone page, which touches nothing. If even that cannot render, a hard-coded line
    goes out with the right status: an error page must never raise."""
    record = ERRORS[key]
    attempts = [("pages/error_plain.html", None)]
    if not plain and hasattr(request, "user"):
        attempts.insert(0, ("pages/error.html", request))
    html = LAST_RESORT
    for template, with_request in attempts:
        try:
            html = render_to_string(template, {"e": record}, request=with_request)
            break
        except Exception:
            log.exception("error page %s: %s failed to render", key, template)
    response = HttpResponse(html, status=record["status"])
    add_never_cache_headers(response)
    return response


def bad_request(request, exception):
    return error_page(request, "400")


def permission_denied(request, exception):
    return error_page(request, "403")


def not_found(request, exception):
    return error_page(request, "404")


def server_error(request):
    return error_page(request, "500", plain=True)


def csrf_failure(request, reason=""):
    return error_page(request, "csrf")
