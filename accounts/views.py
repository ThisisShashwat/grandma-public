from functools import partial

from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView
from django.shortcuts import redirect, render, resolve_url
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_safe

from accounts import onboarding
from accounts.access import has_access, invited
from accounts.forms import LoginForm
from accounts.services import profile_of
from pages.live import live
from talk import flow


class Login(LoginView):
    """Django's login view with our template. A safe `next` is honoured (Django refuses other hosts and other schemes);
    without one, people who have not finished /welcome/ go there and everybody else goes to their dashboard."""
    template_name = "pages/login.html"
    authentication_form = LoginForm
    redirect_authenticated_user = True

    def get_default_redirect_url(self):
        return resolve_url("dashboard" if profile_of(self.request.user).onboarded_at else "welcome")


@invited
def welcome(request):
    """Onboarding. Someone who is already onboarded is sent home, unless this session has just finished it (then they
    still get the last page, with its button home)."""
    store = onboarding.ProfileStore()
    if profile_of(request.user).onboarded_at and not store.load(request).position:
        return redirect("home")
    cfg = live()
    return flow.run(request, onboarding.dialogue(cfg), store=store, finish=partial(onboarding.finish, cfg),
                    then=resolve_url("home"), title="Welcome")


@login_required
@never_cache
@require_safe
def beta(request):
    """Grandma at the door while the site is beta only. Not behind the beta gate (that is where it sends people); somebody who is let in, or
    anybody once BETA_MODE is off, goes on to their dashboard. Nothing about the person is on the page."""
    if has_access(request.user, live()):
        return redirect("dashboard")
    return render(request, "pages/beta.html")
