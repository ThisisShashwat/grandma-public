"""The "signed in" hint for the public pages (todo item 15, 2026-10-07).

The public pages (home, guides, shop, ...) are the same bytes for everybody and never read the session, so a stranger, or somebody sending junk cookies,
cannot make them ask the database anything. The header therefore always arrives as "Sign in", and static/js/core/auth.js swaps it for "Dashboard and Log
out" when this plain cookie says so. The cookie holds nothing about the person (the value is 1), is not HttpOnly on purpose (the script reads it), and
decides nothing: it only picks which links are shown. Every page that needs a person still checks the real session.

It is set at sign-in, cleared at sign-out, and corrected by any request that did look at the session (a signed in page keeps it fresh, a page that finds
nobody signed in clears a stale one). A request that never read the session leaves it alone, so this middleware itself never touches the database.
"""
from django.conf import settings
from django.contrib.auth.signals import user_logged_in, user_logged_out
from django.dispatch import receiver

NAME = "hgo_in"


@receiver(user_logged_in)
def signed_in(sender, request=None, **_):
    if request is not None:
        request._signed_in_flag = True


@receiver(user_logged_out)
def signed_out(sender, request=None, **_):
    if request is not None:
        request._signed_in_flag = False


def flag_of(request):
    """True, False, or None when nothing in this request looked at who is signed in."""
    flag = getattr(request, "_signed_in_flag", None)
    if flag is None and hasattr(request, "_cached_user"):         # set by Django the moment something evaluated request.user
        flag = request._cached_user.is_authenticated
    return flag


def signed_in_flag(get_response):
    def middleware(request):
        response = get_response(request)
        flag = flag_of(request)
        if flag and request.COOKIES.get(NAME) != "1":
            response.set_cookie(NAME, "1", max_age=settings.SESSION_COOKIE_AGE, secure=settings.SESSION_COOKIE_SECURE, httponly=False, samesite="Lax")
        elif flag is False and NAME in request.COOKIES:
            response.delete_cookie(NAME, samesite="Lax")
        return response
    return middleware
