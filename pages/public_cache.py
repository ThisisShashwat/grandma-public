"""A short public cache on the pages that are the same for everybody and read nothing from the database (the home page and the guides).

`Cache-Control: public, max-age=N` lets the visitor's browser reuse a page without asking us, and a shared cache or CDN in front (a host's proxy, a CDN) answer
for us, so a crowd hitting the home page costs the server almost nothing (todo item 15, 2026-10-07). It is only safe because those pages are identical for
everybody (the header is swapped by a script, accounts/signed_in_flag.py) and set no cookie. The price: an admin change (a link, the launch time) and a
deploy show up for up to N seconds. PUBLIC_PAGE_CACHE_SECONDS in the environment sets N (default 60, 0 turns it off). With a preview password the header
says `private`, so a shared cache never keeps a page that was behind the password.
"""
from functools import wraps

from django.conf import settings
from django.utils.cache import patch_cache_control


def public_cache(view):
    @wraps(view)
    def wrapped(request, *args, **kwargs):
        response = view(request, *args, **kwargs)
        seconds = settings.PUBLIC_PAGE_CACHE_SECONDS
        if seconds and request.method in ("GET", "HEAD") and response.status_code == 200 and not response.cookies and "Cache-Control" not in response:
            patch_cache_control(response, max_age=seconds, **{"private" if settings.PREVIEW_PASSWORD else "public": True})
        return response
    return wrapped
