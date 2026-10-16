"""A cap on the size of a request body, checked from the Content-Length header BEFORE anything reads the body (docs/security.md "Request limits").

Django spools an upload to a temporary file before any form sees it, so a form's own size check comes too late to save the disk or the time. Here
a POST (or PUT, PATCH, DELETE) that says it is too big gets a plain 413 and is never read by the site. Two sizes: the pages that take a
picture (the hand-in note, the fix, getting a grant, and the admin's shop item add and change pages with their "upload art" box) may send `UPLOAD_BODY_MAX_MB`;
every other body may send `FORM_BODY_MAX_KB` (the biggest text anybody can type is a few hundred characters). A body with no length (chunked) is refused with 411: browsers always send a length for a form.
The proxy in front should have its own cap too; this is the guard that does not depend on it. Gunicorn still discards the unread bytes."""
import re

from django.conf import settings
from django.http import HttpResponse

SAFE = {"GET", "HEAD", "OPTIONS", "TRACE"}
UPLOAD_PATHS = re.compile(r"^/(submit/(\d+/)?|shop/[^/]+/get/)$")      # submissions: /submit/ and /submit/<pk>/, orders: /shop/<slug>/get/


def reply(status, text):
    return HttpResponse(text, status=status, content_type="text/plain; charset=utf-8")


def admin_art_paths():
    """The admin pages with the shop item's picture box (add, and change of one item), at the admin address the settings give."""
    return re.compile(rf"^/{re.escape(settings.ADMIN_URL)}shop/shopitem/(add|\d+/change)/$")


def body_cap(get_response):
    admin_art = admin_art_paths()

    def middleware(request):
        if request.method in SAFE:
            return get_response(request)
        if "chunked" in request.META.get("HTTP_TRANSFER_ENCODING", "").lower():
            return reply(411, "I need to know how big that is, dear.")
        try:
            length = int(request.META.get("CONTENT_LENGTH") or 0)
        except ValueError:
            return reply(400, "That request is malformed, dear.")
        picture_page = UPLOAD_PATHS.match(request.path_info) or admin_art.match(request.path_info)
        limit = settings.UPLOAD_BODY_MAX_MB * 1024 * 1024 if picture_page else settings.FORM_BODY_MAX_KB * 1024
        if length < 0:
            return reply(400, "That request is malformed, dear.")
        if length > limit:
            return reply(413, "That is far too big, dear.")
        return get_response(request)
    return middleware
