"""The participant's dashboard (/dashboard/) and its two longer lists. For one signed-in, onboarded person, showing only their own
data: no address carries an id. A result waiting at Grandma's sends them to her first (submissions/middleware.py)."""
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_safe

from accounts.access import onboarded
from dashboard import summary
from pages.live import live


@onboarded
@never_cache
@require_safe
def dashboard(request):
    request.session.pop("talk:collect", None)               # Grandma's send-off, if there was one, has been seen
    handed_in = request.session.pop("handed_in", False)     # the note on top after handing a project in, shown once
    return render(request, "pages/dashboard.html", {"dash": summary.build(request.user, live(), timezone.now()), "handed_in": handed_in})


@onboarded
@never_cache
@require_safe
def submissions(request):
    return render(request, "pages/dashboard_submissions.html", {"paged": summary.submissions_page(request.user, request.GET.get("page"))})


@onboarded
@never_cache
@require_safe
def orders(request):
    flash = request.session.pop("order_flash", "")           # what an order just did (placed, taken back, refused), shown once
    return render(request, "pages/dashboard_orders.html", {"paged": summary.orders_page(request.user, request.GET.get("page")), "flash": flash})


@onboarded
@never_cache
@require_safe
def cookies(request):
    return render(request, "pages/dashboard_cookies.html", {"paged": summary.cookies_page(request.user, request.GET.get("page"))})
