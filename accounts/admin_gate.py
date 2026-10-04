"""The admin gate: protects the admin address (docs/owner.md 2026-10-05).

The admin address (settings.ADMIN_URL) is gated:
- Staff members (active, is_staff ticked) pass through.
- Unauthenticated visitors heading to the admin login page (<ADMIN_URL>login/) pass through
  so the superuser can use the password form (guarded by django-axes).
- Authenticated people who are not staff are redirected to the dashboard.
- Unauthenticated visitors trying to reach any other admin page are redirected to /login/
  with the full path in `next` so that staff can sign in via Hack Club and land back in the admin.
Requests outside the admin prefix are passed through untouched.
No logs or cookies are produced by this gate.
"""
from urllib.parse import urlencode

from django.conf import settings
from django.shortcuts import redirect
from django.urls import reverse


def admin_gate(get_response):
    """Gate the admin address per request based on authentication and staff status."""
    def middleware(request):
        prefix = "/" + settings.ADMIN_URL
        if not request.path.startswith(prefix):
            return get_response(request)
        if request.user.is_authenticated:
            if request.user.is_staff and request.user.is_active:
                return get_response(request)
            return redirect("dashboard")
        if request.path == prefix + "login/":
            return get_response(request)
        return redirect(reverse("login") + "?" + urlencode({"next": request.get_full_path()}))
    return middleware
