"""Connecting a Hackatime account (OAuth2, plain: not OpenID Connect). The only module that knows the library (Authlib's Django client). The facts it
rests on and the reasons for each choice: docs/research/hackatime-and-hca.md (section 3 and 5).

WRITTEN DISABLED, for the owner to review before he enables it: nothing here runs unless the HACKATIME_ENABLED admin setting is on AND HACKATIME_CLIENT_ID
and HACKATIME_CLIENT_SECRET are in the environment (`enabled`), and the library is only set up the first time it is needed. Until then the Hackatime step
of onboarding is the old greyed-out button (accounts/script.py).

Hackatime is asked for two scopes (profile read: `profile` cannot be left out) and we keep ONE fact: the person's Hackatime user id, so one Hackatime
account cannot back two accounts here. The token is the danger (even a `profile` token can read the person's Hackatime API key, which can fake hours),
so it is used for one call and revoked at once: never stored, never logged, never put in the session. The answer of that call carries emails: it is
read in memory and dropped, nothing but the id leaves `read_identity`.
"""
from authlib.integrations.django_client import OAuth
from django.conf import settings
from django.db import transaction
from django.urls import reverse

from accounts.models import Profile
from audit import services as audit

NAME = "hackatime"
SCOPE = "profile read"
TIMEOUT_SECONDS = 5
ID_MAX_LENGTH = 40

oauth = OAuth()


def enabled(cfg):
    """Is connecting Hackatime on? `cfg` is pages.live.live()."""
    return bool(cfg.HACKATIME_ENABLED and settings.HACKATIME_CLIENT_ID and settings.HACKATIME_CLIENT_SECRET)


def client():
    """The Hackatime app, registered on first use from the settings (importing this module with no credentials does nothing). Authlib makes the
    state and keeps it in the session, and checks it when the person comes back."""
    base = settings.HACKATIME_BASE_URL.rstrip("/")
    return oauth.create_client(NAME) or oauth.register(
        NAME, client_id=settings.HACKATIME_CLIENT_ID, client_secret=settings.HACKATIME_CLIENT_SECRET,
        authorize_url=f"{base}/oauth/authorize", access_token_url=f"{base}/oauth/token", api_base_url=f"{base}/",
        client_kwargs={"scope": SCOPE, "token_endpoint_auth_method": "client_secret_post", "default_timeout": TIMEOUT_SECONDS})


def redirect_uri():
    return settings.SITE_URL.rstrip("/") + reverse("connect_hackatime_callback")


def authorize_redirect(request):
    """The redirect to Hackatime, with the state saved in the session."""
    return client().authorize_redirect(request, redirect_uri())


def read_identity(token):
    """The person's Hackatime user id as a string, from GET api/v1/authenticated/me, and nothing else: the answer has emails, a Slack ID and a GitHub name,
    and none of it is kept. ASSUMED (research 3.3, from the docs and swagger, not run live): the body is a JSON object whose `id` is an integer. A missing,
    empty, boolean or over-long id raises."""
    response = client().get("api/v1/authenticated/me", token=token)
    response.raise_for_status()
    value = response.json()["id"]
    if isinstance(value, bool) or not isinstance(value, (int, str)):
        raise ValueError
    hackatime_id = str(value).strip()
    if not 0 < len(hackatime_id) <= ID_MAX_LENGTH:
        raise ValueError
    return hackatime_id


def revoke(token):
    """Ask Hackatime to forget the token (POST oauth/revoke with the token and the app's id and secret, form encoded). Best effort: it never raises, because
    a failure here must not undo a connection that worked. ASSUMED (research 3.2): the endpoint takes these three fields and answers 200 whatever happens."""
    try:
        client().post("oauth/revoke", withhold_token=True, data={
            "token": token["access_token"], "client_id": settings.HACKATIME_CLIENT_ID, "client_secret": settings.HACKATIME_CLIENT_SECRET})
    except Exception:
        pass


def identity_of(request):
    """The Hackatime user id of the connection the person has just made, or None when anything at all went wrong (a refusal at Hackatime, a stale or
    forged state, a bad code, no network, an answer in a shape we do not know). Whatever happened, a token that was handed over is revoked here, and
    dropped: it never leaves this function."""
    try:
        token = client().authorize_access_token(request)
    except Exception:
        return None
    try:
        return read_identity(token)
    except Exception:
        return None
    finally:
        revoke(token)


def link(profile, hackatime_id):
    """Connect this Profile to this Hackatime account: True, or False to refuse. Refused: an id that already belongs to another Profile, a Profile
    already connected to a different id (it stays put, so a banned or unlucky account cannot be swapped for a clean one), an inactive user. The same
    id again is fine. The Profile row is locked, and the audit entry is written in the same transaction (nothing about Hackatime goes in it)."""
    with transaction.atomic():
        stored = Profile.objects.select_for_update().select_related("user").get(pk=profile.pk)
        taken = Profile.objects.filter(hackatime_user_id=hackatime_id).exclude(pk=stored.pk).exists()
        if taken or not stored.user.is_active or stored.hackatime_user_id not in (None, hackatime_id):
            return False
        stored.hackatime_user_id, stored.hackatime_connected = hackatime_id, True
        stored.save(update_fields=["hackatime_user_id", "hackatime_connected"])
        audit.record("accounts.hackatime_connect", actor=stored.user, subject=stored.user, target=stored, details={})
    return True
