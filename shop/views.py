from django.shortcuts import render
from django.views.decorators.http import require_safe

from accounts.models import Profile
from ledger import services as ledger

from . import catalog


def jar_of(user):
    """The cookies in this person's jar, or None for a visitor (anonymous, or signed in but not finished at /welcome/): only an
    onboarded person may buy, so only they get the buttons and their balance (docs/orders.md)."""
    if user.is_authenticated and Profile.objects.filter(user=user, onboarded_at__isnull=False).exists():
        return ledger.balance(user)
    return None


@require_safe
def shop(request):
    return render(request, "pages/shop.html", {"shop": catalog.build(), "jar": jar_of(request.user)})
