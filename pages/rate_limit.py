"""Request rate limits for the whole site (docs/security.md "Request limits"). Fixed one minute windows, counted per client address and, for a
POST, also per session cookie (hashed). Over the limit: a plain 429 with Retry-After. The sign-in lockout (django-axes) stays as it is.

What is counted: a GET per address in this process's memory (cheap on purpose: the public pages make no database query and must stay fast, so with
several workers the real limit is a few times the number); a POST per address and per session in the shared cache table, and the sign-in and
connect addresses per address in the shared table. Static files never get here (WhiteNoise answers them first) and the health probes are exempt.
Keys hold a hash of the address and of the session cookie, never the value itself, and expire within a minute. If the shared store is down the
request goes through (a limit must never be what takes the site down). With the site behind a proxy and AXES_PROXY_COUNT left at 0, or with fewer
X-Forwarded-For entries than AXES_PROXY_COUNT, the address is the proxy's, the same for everybody, so the address rules are skipped (the session rule
still applies): set AXES_PROXY_COUNT to the number of proxies.
Every number is an environment setting; RATE_LIMITS_ENABLED=False switches the lot off."""
import hashlib
import logging
import re
import time

from django.conf import settings
from django.core.cache import caches
from django.http import HttpResponse

from accounts.clientip import client_ip
from pages.body_cap import SAFE

log = logging.getLogger("grandma.ratelimit")
EXEMPT = ("/healthz", "/readyz")
SIGN_IN = re.compile(r"^/(login|connect|hackatime)/")
WINDOW = 60


def digest(value):
    return hashlib.sha256(f"{settings.SECRET_KEY}|{value}".encode()).hexdigest()[:20]


def count(alias, key):
    """How many times `key` has been seen in this minute, this one included."""
    cache = caches[alias]
    name = f"rl:{key}:{int(time.time() // WINDOW)}"
    try:                                    # incr first: an add on a key that exists makes the database cache run a failing INSERT (Postgres logs it)
        return cache.incr(name)
    except ValueError:                      # no counter yet this minute
        pass
    if cache.add(name, 1, WINDOW + 5):
        return 1
    try:                                    # another request made it between our two calls
        return cache.incr(name)
    except ValueError:                      # it expired in between: this one is the first
        return 1


def address_known(request):
    """Is client_ip the client's own address? Behind a proxy only with a count of 1 or more AND at least that many X-Forwarded-For entries: with fewer,
    client_ip falls back to REMOTE_ADDR (the proxy's own), the same for everybody, and counting it would 429 the whole site together."""
    if not settings.BEHIND_PROXY:
        return True
    entries = [part for part in request.META.get("HTTP_X_FORWARDED_FOR", "").split(",") if part.strip()]
    return 1 <= settings.TRUSTED_PROXY_COUNT <= len(entries)


def checks(request):
    """(alias, key, limit) for every rule this request falls under."""
    out = []
    ip = digest(client_ip(request) or "unknown") if address_known(request) else None
    if request.method in SAFE:
        if ip:
            out.append(("ratelimit_local", f"get:{ip}", settings.RATE_LIMIT_GET))
    else:
        if ip:
            out.append(("ratelimit", f"post:{ip}", settings.RATE_LIMIT_POST_IP))
        session = request.COOKIES.get(settings.SESSION_COOKIE_NAME)
        if session:
            out.append(("ratelimit", f"session:{digest(session)}", settings.RATE_LIMIT_POST_SESSION))
    if ip and SIGN_IN.match(request.path_info):
        out.append(("ratelimit", f"auth:{ip}", settings.RATE_LIMIT_SIGN_IN))
    return out


def rate_limit(get_response):
    def middleware(request):
        if not settings.RATE_LIMITS_ENABLED or request.path_info.rstrip("/") in EXEMPT:
            return get_response(request)
        try:
            for alias, key, limit in checks(request):
                if count(alias, key) > limit:
                    wait = WINDOW - int(time.time()) % WINDOW
                    return HttpResponse("Too many requests, dear. Slow down and try again in a minute.", status=429,
                                        content_type="text/plain; charset=utf-8", headers={"Retry-After": str(wait)})
        except Exception:                   # the store is down: let the request through, say so once per failure, never what was asked
            log.warning("rate limit store unavailable; request let through")
        return get_response(request)
    return middleware
