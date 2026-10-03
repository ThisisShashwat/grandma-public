from functools import partial

from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView
from django.shortcuts import redirect, resolve_url

from accounts import onboarding
from accounts.forms import LoginForm
from accounts.services import profile_of
from pages.live import live
from talk import flow


class Login(LoginView):
    """Django's login view with our template. A safe `next` is honoured (Django refuses other hosts and other schemes);
    without one, people who have not finished /welcome/ go there and everybody else goes home."""
    template_name = "pages/login.html"
    authentication_form = LoginForm
    redirect_authenticated_user = True

    def get_default_redirect_url(self):
        return resolve_url("home" if profile_of(self.request.user).onboarded_at else "welcome")


@login_required
def welcome(request):
    """Onboarding. Someone who is already onboarded is sent home, unless this session has just finished it (then they
    still get the last page, with its button home)."""
    store = onboarding.ProfileStore()
    if profile_of(request.user).onboarded_at and not store.load(request).position:
        return redirect("home")
    cfg = live()
    return flow.run(request, onboarding.dialogue(cfg), store=store, finish=partial(onboarding.finish, cfg),
                    then=resolve_url("home"), title="Welcome")
