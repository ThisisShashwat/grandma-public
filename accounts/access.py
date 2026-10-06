from functools import wraps

from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect

from accounts.services import profile_of, request_profile
from pages.live import live


def has_access(user, cfg, request=None):
    """May this signed-in person use the participant pages? Everybody once BETA_MODE is off; while it is on, staff and the people given
    beta access. `cfg` is pages.live.live(). With the `request` the Profile is the one read once for the request."""
    return not cfg.BETA_MODE or user.is_staff or user.is_superuser or (request_profile(request) if request is not None else profile_of(user)).beta_access


def invited(view):
    """The first gate of every page that needs a person: logged in (else /login/) and let in (else /beta/, before anything else, so
    somebody without access never starts onboarding)."""
    @wraps(view)
    @login_required
    def gated(request, *args, **kwargs):
        if not has_access(request.user, live(), request):
            return redirect("beta")
        return view(request, *args, **kwargs)
    return gated


def onboarded(view):
    """For every page that needs a person: they must be logged in (else /login/), let in (else /beta/) and have finished /welcome/
    (else they are sent there). Public pages never use it."""
    @wraps(view)
    @invited
    def gated(request, *args, **kwargs):
        if request_profile(request).onboarded_at is None:
            return redirect("welcome")
        return view(request, *args, **kwargs)
    return gated
