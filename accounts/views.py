import logging
from functools import partial

from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView
from django.http import Http404
from django.shortcuts import redirect, render, resolve_url
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_safe

from accounts import hca, onboarding
from accounts.access import has_access, invited
from accounts.forms import LoginForm
from accounts.script import HCA_REFUSALS
from accounts.services import profile_of
from pages.live import live
from talk import flow


log = logging.getLogger(__name__)
HCA_NEXT = "hca_next"        # the session key that carries the safe `next` over to the callback


def landing(user):
    """Where somebody goes after signing in with nothing asked for: /welcome/ until they have finished it, then their dashboard."""
    return resolve_url("dashboard" if profile_of(user).onboarded_at else "welcome")


class Login(LoginView):
    """Django's login view with our template. A safe `next` is honoured (Django refuses other hosts and other schemes);
    without one, people who have not finished /welcome/ go there and everybody else goes to their dashboard."""
    template_name = "pages/login.html"
    authentication_form = LoginForm
    redirect_authenticated_user = True

    def get_default_redirect_url(self):
        return landing(self.request.user)

    def get_context_data(self, **kwargs):
        return super().get_context_data(**kwargs) | {"hackclub": hca.enabled(live())}


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


def hackclub_refused(request, reason):
    """Grandma's page for a Hack Club sign-in that did not go through: one fixed sentence per reason, nothing from the request or from Hack Club.
    Only a failure that is nobody's fault is a 400; a refusal is a 403."""
    label, line = HCA_REFUSALS[reason]
    return render(request, "pages/hackclub_refused.html", {"label": label, "line": line}, status=400 if reason == "failed" else 403)


@never_cache
@require_GET
def login_hackclub(request):
    """Sends the person to Hack Club to sign in. Only the `next` that is safe (this host, this scheme) is kept, in the session, before leaving;
    the callback never takes a redirect target from its own request."""
    if not hca.enabled(live()):
        raise Http404
    target = request.GET.get("next", "")
    safe = url_has_allowed_host_and_scheme(target, allowed_hosts={request.get_host()}, require_https=request.is_secure())
    request.session[HCA_NEXT] = target if safe else ""
    try:
        return hca.authorize_redirect(request)
    except Exception:
        log.warning("hack club sign-in failed")
        return hackclub_refused(request, "failed")


@never_cache
@require_GET
def login_hackclub_callback(request):
    """Where Hack Club sends the person back. The library checks the state, the code and the id token; then the eligibility rules, then the
    account (docs/accounts.md). Nothing is created: an unknown person is refused. The Django login uses the named backend (Axes guards passwords
    only, and two backends are configured). No token is kept."""
    cfg = live()
    if not hca.enabled(cfg):
        raise Http404
    target = request.session.pop(HCA_NEXT, "")
    userinfo = hca.userinfo_of(request)
    if userinfo is None:
        log.warning("hack club sign-in failed")
        return hackclub_refused(request, "failed")
    ok, reason = hca.check(userinfo, cfg.HCA_REQUIRE_ELIGIBLE)
    if not ok:
        return hackclub_refused(request, reason)
    profile = hca.identify(userinfo)
    if profile is None:
        return hackclub_refused(request, "no_account")
    login(request, profile.user, backend="django.contrib.auth.backends.ModelBackend")
    return redirect(target or landing(profile.user))
