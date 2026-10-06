import logging
from functools import partial
from urllib.parse import urlencode, urlsplit

from django.conf import settings
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView
from django.http import Http404, HttpResponseNotAllowed, HttpResponseRedirect
from django.shortcuts import redirect, render, resolve_url
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_safe

from accounts import hackatime, hca, onboarding
from accounts.access import has_access, invited
from accounts.forms import LoginForm
from accounts.script import HACKATIME_REFUSALS, HCA_REFUSALS
from accounts.services import profile_of
from pages.live import live
from talk import flow


log = logging.getLogger(__name__)
HCA_NEXT = "hca_next"        # the session key that carries the safe `next` over to the callback
HACKATIME_NEXT = "hackatime_next"


def landing(user):
    """Where somebody goes after signing in with nothing asked for: /welcome/ until they have finished it, then their dashboard."""
    return resolve_url("dashboard" if profile_of(user).onboarded_at else "welcome")


class Login(LoginView):
    """Django's login view with our template. A safe `next` is honoured (Django refuses other hosts and other schemes);
    without one, people who have not finished /welcome/ go there and everybody else goes to their dashboard."""
    template_name = "pages/login.html"
    authentication_form = LoginForm
    redirect_authenticated_user = True

    def dispatch(self, request, *args, **kwargs):
        if hca.enabled(live()) and not request.user.is_authenticated:
            if request.method in ("GET", "HEAD"):
                url = reverse("login_hackclub")
                nxt = safe_next(request)
                if nxt:
                    url = f"{url}?{urlencode({'next': nxt})}"
                return redirect(url)
            return HttpResponseNotAllowed(["GET", "HEAD"])
        if not request.user.is_authenticated and not hca.enabled(live()) and not settings.PASSWORD_LOGIN:
            raise Http404
        return super().dispatch(request, *args, **kwargs)

    def get_default_redirect_url(self):
        return landing(self.request.user)


@invited
@never_cache
def welcome(request):
    """Onboarding. Someone who is already onboarded is sent to their dashboard, unless this session has just finished it (then they
    still get the last page, with its button to the dashboard)."""
    store = onboarding.ProfileStore()
    profile = profile_of(request.user)
    if profile.onboarded_at and not store.load(request).position:
        return redirect("dashboard")
    cfg = live()
    return flow.run(request, onboarding.dialogue(cfg, profile.hackatime_connected, slack_known=bool(profile.hca_sub and profile.slack_id)),
                    store=store, finish=partial(onboarding.finish, cfg),
                    then=resolve_url("dashboard"), title="Welcome")


@login_required
@never_cache
@require_safe
def beta(request):
    """Grandma at the door while the site is beta only. Not behind the beta gate (that is where it sends people); somebody who is let in, or
    anybody once BETA_MODE is off, goes on to their dashboard. Nothing about the person is on the page."""
    if has_access(request.user, live()):
        return redirect("dashboard")
    return render(request, "pages/beta.html")


def safe_next(request):
    """The `next` of the request when it is safe (this host, this scheme), else an empty string. Kept in the session before a person leaves for another
    service: the callback never takes a redirect target from its own request."""
    target = request.GET.get("next", "")
    safe = url_has_allowed_host_and_scheme(target, allowed_hosts={request.get_host()}, require_https=request.is_secure())
    if not safe:
        return ""
    login_path = reverse("login")
    target_path = urlsplit(target).path
    if target_path == login_path or target_path.startswith(login_path) or target_path == login_path.rstrip("/"):
        return ""
    return target


def after_sign_in(target, user):
    """Where a person goes once back from another service: the safe `next` kept in the session as a plain address (never as a URL name, which `redirect`
    would try first and fail on a bare word), else where they belong."""
    return HttpResponseRedirect(target) if target else redirect(landing(user))


def hackclub_refused(request, reason):
    """Grandma's page for a Hack Club sign-in that did not go through: one fixed sentence per reason, nothing from the request or from Hack Club.
    Only a failure that is nobody's fault is a 400; a refusal is a 403."""
    label, line = HCA_REFUSALS[reason]
    return render(request, "pages/hackclub_refused.html", {"label": label, "line": line}, status=400 if reason == "failed" else 403)


@never_cache
@require_GET
def login_hackclub(request):
    """Sends the person to Hack Club to sign in. Only a safe `next` is kept, in the session, before leaving."""
    if not hca.enabled(live()):
        raise Http404
    request.session[HCA_NEXT] = safe_next(request)
    try:
        return hca.authorize_redirect(request)
    except Exception:
        log.warning("hack club sign-in failed")
        return hackclub_refused(request, "failed")


@never_cache
@require_GET
def login_hackclub_callback(request):
    """Where Hack Club sends the person back. The library checks the state, the code and the id token; then hca.identify
    signs in a returning person or creates an account on first login. The Django login uses the named backend (Axes guards
    passwords only, and two backends are configured). No token is kept."""
    cfg = live()
    if not hca.enabled(cfg):
        raise Http404
    target = request.session.pop(HCA_NEXT, "")
    userinfo = hca.userinfo_of(request)
    if userinfo is None:
        log.warning("hack club sign-in failed")
        return hackclub_refused(request, "failed")
    profile, reason = hca.identify(userinfo, cfg.HCA_REQUIRE_ELIGIBLE)
    if reason is not None:
        log.warning("hack club sign-in refused: %s", reason)
        return hackclub_refused(request, reason)
    login(request, profile.user, backend="django.contrib.auth.backends.ModelBackend")
    return after_sign_in(target, profile.user)


def hackatime_refused(request, reason):
    """Grandma's page for a Hackatime connection that did not go through: one fixed sentence per reason, nothing from the request or from Hackatime.
    The way back is onboarding (they are signed in). Only a failure that is nobody's fault is a 400; a refusal is a 403."""
    label, line = HACKATIME_REFUSALS[reason]
    context = {"label": label, "line": line, "back_url": resolve_url("welcome"), "back_label": "Back to Grandma"}
    return render(request, "pages/hackclub_refused.html", context, status=400 if reason == "failed" else 403)


@invited
@never_cache
@require_GET
def connect_hackatime(request):
    """Sends the person to Hackatime to connect their account: part of onboarding, so it needs a person who is let in but not one who has finished
    /welcome/. 404 until it is switched on. A safe `next` is kept in the session before leaving."""
    if not hackatime.enabled(live()):
        raise Http404
    request.session[HACKATIME_NEXT] = safe_next(request)
    try:
        return hackatime.authorize_redirect(request)
    except Exception:
        log.warning("hackatime connect failed")
        return hackatime_refused(request, "failed")


@invited
@never_cache
@require_GET
def connect_hackatime_callback(request):
    """Where Hackatime sends the person back. The library checks the state and the code, we read the Hackatime user id,
    seal the token (accounts/hackatime.py), then link it to this person's Profile. Back to the safe `next`, else to where they were."""
    if not hackatime.enabled(live()):
        raise Http404
    target = request.session.pop(HACKATIME_NEXT, "")
    connection = hackatime.identity_of(request)
    if connection is None:
        log.warning("hackatime connect failed")
        return hackatime_refused(request, "failed")
    if not hackatime.link(profile_of(request.user), connection.hackatime_id, connection.slack_id, connection.sealed, connection.github_username):
        hackatime.discard(connection.sealed)
        return hackatime_refused(request, "taken")
    return after_sign_in(target, request.user)
