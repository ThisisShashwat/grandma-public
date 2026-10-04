from django.shortcuts import render
from django.views.decorators.http import require_safe

from accounts.access import has_access
from accounts.models import Profile
from ledger import services as ledger
from pages.live import live

from . import catalog


def jar_of(user):
    """The cookies in this person's jar, or None for a visitor (anonymous, signed in but not finished at /welcome/, or turned away by the
    beta gate): only an onboarded person who is let in may buy, so only they get the buttons and their balance (docs/orders.md)."""
    if user.is_authenticated and Profile.objects.filter(user=user, onboarded_at__isnull=False).exists() and has_access(user, live()):
        return ledger.balance(user)
    return None


@require_safe
def shop(request):
    return render(request, "pages/shop.html", {"shop": catalog.build(), "jar": jar_of(request.user)})
