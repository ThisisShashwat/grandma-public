"""The admin gate: protects the admin address (docs/owner.md 2026-10-05).

The admin address (settings.ADMIN_URL) is gated:
- Staff members (is_staff ticked) pass through (a deactivated user is anonymous by the time the gate runs).
- Unauthenticated visitors heading to the admin login page (<ADMIN_URL>login/) pass through
  so the superuser can use the password form (guarded by django-axes).
- Authenticated people who are not staff are redirected to the dashboard.
- Unauthenticated visitors trying to reach any other admin page are redirected to /login/
  with the full path in `next` so that staff can sign in via Hack Club and land back in the admin.
Requests outside the admin prefix are passed through untouched.
No logs or cookies are produced by this gate.
Staff see the admin's times in their OWN time zone (the one on their Profile, given in onboarding), else settings.TIME_ZONE; only inside the admin.
"""
from urllib.parse import urlencode
from zoneinfo import ZoneInfo

from django.conf import settings
from django.shortcuts import redirect
from django.urls import reverse
from django.utils import timezone

from accounts.services import request_profile
from accounts.validators import canonical_timezone


def own_zone(request):
    """The staff member's own zone, or None (no profile zone, or one the system does not know)."""
    name = canonical_timezone(request_profile(request).timezone)
    try:
        return ZoneInfo(name) if name else None
    except (KeyError, ValueError, OSError):
        return None


def admin_gate(get_response):
    """Gate the admin address per request based on authentication and staff status."""
    def middleware(request):
        prefix = "/" + settings.ADMIN_URL
        if not request.path_info.startswith(prefix):
            return get_response(request)
        if request.user.is_authenticated:
            if request.user.is_staff:
                zone = own_zone(request)
                if zone is not None:
                    timezone.activate(zone)
                    try:
                        return get_response(request)
                    finally:
                        timezone.deactivate()
                return get_response(request)
            return redirect("dashboard")
        if request.path_info == prefix + "login/":
            return get_response(request)
        return redirect(reverse("login") + "?" + urlencode({"next": request.get_full_path()}))
    return middleware
