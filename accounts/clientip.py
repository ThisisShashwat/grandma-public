"""The address a failed sign-in is counted against (django-axes, AXES_CLIENT_IP_CALLABLE). REMOTE_ADDR, and nothing a client sends, unless
the owner says reverse proxies stand in front (AXES_PROXY_COUNT above 0 in the environment): then it is the address the nearest trusted proxy
saw, which is that many places from the right in X-Forwarded-For (everything further left is the client's own claim and is ignored)."""
from ipaddress import ip_address

from django.conf import settings


def client_ip(request):
    remote = request.META.get("REMOTE_ADDR")
    count = settings.TRUSTED_PROXY_COUNT
    forwarded = [part.strip() for part in request.META.get("HTTP_X_FORWARDED_FOR", "").split(",") if part.strip()]
    if count < 1 or len(forwarded) < count:
        return remote
    return forwarded[-count] if is_address(forwarded[-count]) else remote


def is_address(text):
    try:
        ip_address(text)
    except ValueError:
        return False
    return True
