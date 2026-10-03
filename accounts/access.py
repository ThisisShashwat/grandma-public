from functools import wraps

from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect

from accounts.services import profile_of


def onboarded(view):
    """For every page that needs a person: they must be logged in (else /login/) and have finished /welcome/ (else they
    are sent there). Public pages never use it."""
    @wraps(view)
    @login_required
    def gated(request, *args, **kwargs):
        if profile_of(request.user).onboarded_at is None:
            return redirect("welcome")
        return view(request, *args, **kwargs)
    return gated
