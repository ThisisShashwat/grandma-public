from django.shortcuts import render
from django.utils.cache import add_never_cache_headers
from django.views.decorators.http import require_safe

from accounts.access import has_access
from accounts.models import Profile
from ledger import services as ledger
from pages.live import live
from submissions.services import holds_ribbon_user

from . import catalog


def standing(user):
    """What the Pantry's header needs of a person: (their jar, why they cannot spend yet). Only an onboarded person who is let in may buy, so
    only they get the buttons and their balance: (cookies, ""). A visitor is (None, ""). A signed in person who cannot buy yet is
    (None, "beta") when the beta gate has not let them in, or (None, "welcome") when they have not finished at /welcome/ (docs/orders.md)."""
    if not user.is_authenticated:
        return None, ""
    if not has_access(user, live()):
        return None, "beta"
    if not Profile.objects.filter(user=user, onboarded_at__isnull=False).exists():
        return None, "welcome"
    return ledger.balance(user), ""


@require_safe
def shop(request):
    """The public Pantry. Everybody sees every active item; the ribbon only ones show locked unless the viewer holds a Blue Ribbon. Someone who is signed in
    and let in also sees their jar: those responses, and a holder's (their ribbon only cards are not locked), are never cached."""
    (jar, held), ribbon = standing(request.user), holds_ribbon_user(request.user)
    response = render(request, "pages/shop.html", {"shop": catalog.build(ribbon=ribbon), "jar": jar, "held": held})
    if jar is not None or ribbon:
        add_never_cache_headers(response)
    return response
