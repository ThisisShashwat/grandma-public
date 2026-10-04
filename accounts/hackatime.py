"""Connecting a Hackatime account (OAuth2, plain: not OpenID Connect). The only module that knows the library (Authlib's Django client). The facts it
rests on and the reasons for each choice: docs/research/hackatime-and-hca.md (section 3 and 5).

WRITTEN DISABLED, for the owner to review before he enables it: nothing here runs unless the HACKATIME_ENABLED admin setting is on AND HACKATIME_CLIENT_ID
and HACKATIME_CLIENT_SECRET are in the environment (`enabled`), and the library is only set up the first time it is needed. Until then the Hackatime step
of onboarding is the old greyed-out button (accounts/script.py).

Hackatime is asked for two scopes (profile read: `profile` cannot be left out) and we keep the person's Hackatime user id and the access token
encrypted at rest (HACKATIME_TOKEN_KEYS). Never logged, never shown, never in the admin, never in the session. The answer of that call carries emails:
it is read in memory and dropped, nothing but the id and the Slack ID (which is only compared with the Profile's, never stored) leaves `read_identity`.

The same connection is made again, on purpose, at hand-in to count the hours of one Hackatime project (`seconds_of`, the "Check my hours" button of the
submit note): connect, check it is the account that was connected, read ONE number, revoke. Nothing but that number leaves the module, and it is for
reviewers only: a participant never sees it (docs/submissions.md).
"""
from datetime import timedelta, timezone
from typing import NamedTuple

from authlib.integrations.django_client import OAuth
from cryptography.fernet import Fernet, InvalidToken, MultiFernet
from django.conf import settings
from django.db import transaction
from django.urls import reverse
from django.views.decorators.debug import sensitive_variables

from accounts.models import Profile
from audit import services as audit

NAME = "hackatime"
SCOPE = "profile read"
TIMEOUT_SECONDS = 5
ID_MAX_LENGTH = 40
NAME_MAX_LENGTH = 100                      # the longest Hackatime project name we ask about (Project.tracked_name, a test pins them together)
MAX_SECONDS = 2**31 - 1                    # what the database column holds
MIN_SECONDS = 600                          # when hours are required: a ten-minute floor, so one stray heartbeat is not "work" (code, not a setting)
FRESH_FOR = timedelta(hours=24)            # when hours are required: a check older than this is made again


class TokenUnreadable(Exception):
    """The stored token is empty, corrupted, or cannot be decrypted."""


class Connection(NamedTuple):
    """A verified Hackatime identity and its sealed access token."""

    hackatime_id: str
    slack_id: str | None
    sealed: str


oauth = OAuth()


def enabled(cfg):
    """Is connecting Hackatime on? `cfg` is pages.live.live()."""
    return bool(cfg.HACKATIME_ENABLED and settings.HACKATIME_CLIENT_ID and settings.HACKATIME_CLIENT_SECRET)


def required(cfg):
    """Must a project have checked hours to be handed in? Only while Hackatime is on, or nobody could ever hand anything in."""
    return bool(cfg.HACKATIME_REQUIRED) and enabled(cfg)


def client():
    """The Hackatime app, registered on first use from the settings (importing this module with no credentials does nothing). Authlib makes the
    state and keeps it in the session, and checks it when the person comes back."""
    base = settings.HACKATIME_BASE_URL.rstrip("/")
    return oauth.create_client(NAME) or oauth.register(
        NAME, client_id=settings.HACKATIME_CLIENT_ID, client_secret=settings.HACKATIME_CLIENT_SECRET,
        authorize_url=f"{base}/oauth/authorize", access_token_url=f"{base}/oauth/token", api_base_url=f"{base}/",
        client_kwargs={"scope": SCOPE, "token_endpoint_auth_method": "client_secret_post", "default_timeout": TIMEOUT_SECONDS})


def redirect_uri(callback="connect_hackatime_callback"):
    """The address Hackatime sends the person back to: the connect callback, or (named) the one of the hours check. Both must be registered at Hackatime."""
    return settings.SITE_URL.rstrip("/") + reverse(callback)


def authorize_redirect(request, callback="connect_hackatime_callback"):
    """The redirect to Hackatime, with the state (and the address to come back to) saved in the session."""
    return client().authorize_redirect(request, redirect_uri(callback))


@sensitive_variables("token")
def read_identity(token):
    """(the person's Hackatime user id as a string, their Slack ID or None), from GET api/v1/authenticated/me, and nothing else: the answer has emails and
    a GitHub name, and none of it is kept (the Slack ID is only compared with the one on the Profile, never stored). ASSUMED (research 3.3, from the docs
    and swagger, not run live): the body is a JSON object whose `id` is an integer and whose `slack_id` is text, null or missing. A missing, empty,
    boolean or over-long id, or a Slack ID that is not text, raises."""
    response = client().get("api/v1/authenticated/me", token=token)
    response.raise_for_status()
    body = response.json()
    value, slack_id = body["id"], body.get("slack_id")
    if isinstance(value, bool) or not isinstance(value, (int, str)) or not (slack_id is None or isinstance(slack_id, str)):
        raise ValueError
    hackatime_id = str(value).strip()
    if not 0 < len(hackatime_id) <= ID_MAX_LENGTH:
        raise ValueError
    return hackatime_id, slack_id or None


@sensitive_variables("token")
def revoke(token):
    """Ask Hackatime to forget the token (POST oauth/revoke with the token and the app's id and secret, form encoded). Best effort: it never raises, because
    a failure here must not undo a connection that worked. ASSUMED (research 3.2): the endpoint takes these three fields and answers 200 whatever happens."""
    try:
        client().post("oauth/revoke", withhold_token=True, data={
            "token": token["access_token"], "client_id": settings.HACKATIME_CLIENT_ID, "client_secret": settings.HACKATIME_CLIENT_SECRET})
    except Exception:
        pass


@sensitive_variables("access_token")
def seal(access_token):
    """Encrypt the access token with MultiFernet using settings.HACKATIME_TOKEN_KEYS.
    The first key encrypts. Raises TokenUnreadable if no keys are configured or encryption fails."""
    keys = getattr(settings, "HACKATIME_TOKEN_KEYS", [])
    if not keys:
        raise TokenUnreadable
    try:
        fernet = MultiFernet([Fernet(k) for k in keys])
        token_bytes = access_token.encode("utf-8") if isinstance(access_token, str) else access_token
        return fernet.encrypt(token_bytes).decode("utf-8")
    except TokenUnreadable:
        raise
    except Exception:
        raise TokenUnreadable from None


@sensitive_variables("plain", "ciphertext")
def unseal(ciphertext):
    """Decrypt the ciphertext into the plain access token string using settings.HACKATIME_TOKEN_KEYS.
    Raises TokenUnreadable for an empty value, a bad token, or no matching key.
    Never puts ciphertext or plaintext in the exception."""
    if not ciphertext:
        raise TokenUnreadable
    keys = getattr(settings, "HACKATIME_TOKEN_KEYS", [])
    if not keys:
        raise TokenUnreadable
    try:
        fernet = MultiFernet([Fernet(k) for k in keys])
        cipher_bytes = ciphertext.encode("utf-8") if isinstance(ciphertext, str) else ciphertext
        return fernet.decrypt(cipher_bytes).decode("utf-8")
    except InvalidToken:
        raise TokenUnreadable from None
    except TokenUnreadable:
        raise
    except Exception:
        raise TokenUnreadable from None


@sensitive_variables("plain")
def token_of(profile):
    """{"access_token": <plain>, "token_type": "Bearer"} ready for Authlib's client().get(..., token=...),
    or None when the profile has no token or it is unreadable."""
    if not profile or not getattr(profile, "hackatime_token", None):
        return None
    try:
        plain = unseal(profile.hackatime_token)
        return {"access_token": plain, "token_type": "Bearer"}
    except TokenUnreadable:
        return None


def discard(sealed):
    """Best effort and never raising: unseal and revoke it (used when a token was handed over but not kept)."""
    try:
        plain = unseal(sealed)
        revoke({"access_token": plain})
    except Exception:
        pass


@sensitive_variables("token")
def identity_of(request):
    """Connection(hackatime_id, slack_id, sealed) of the connection the person has just made, or None when anything
    at all went wrong. Whatever happened after the token was handed over, it is revoked. On success it is kept sealed."""
    try:
        token = client().authorize_access_token(request)
    except Exception:
        return None
    keep = False
    try:
        hackatime_id, slack_id = read_identity(token)
        sealed = seal(token["access_token"])
        keep = True
        return Connection(hackatime_id, slack_id, sealed)
    except Exception:
        return None
    finally:
        if not keep:
            revoke(token)


def link(profile, hackatime_id, slack_id=None, sealed=""):
    """Connect this Profile to this Hackatime account: True, or False to refuse. Refused: an id that already belongs to another Profile, a Profile
    already connected to a different id (it stays put, so a banned or unlucky account cannot be swapped for a clean one), an inactive user, and a
    Hackatime account that names another Slack ID than the one on the Profile (`slack_id` is only compared, never stored; a missing one on either side
    passes: it is a signal, not proof). The same id again is fine and replaces the token (reconnect). The Profile row is locked, and the audit entry
    is written in the same transaction (nothing about Hackatime goes in it)."""
    with transaction.atomic():
        stored = Profile.objects.select_for_update().select_related("user").get(pk=profile.pk)
        taken = Profile.objects.filter(hackatime_user_id=hackatime_id).exclude(pk=stored.pk).exists()
        somebody_else = bool(slack_id and stored.slack_id and slack_id != stored.slack_id)
        if taken or somebody_else or not stored.user.is_active or stored.hackatime_user_id not in (None, hackatime_id):
            return False
        stored.hackatime_user_id = hackatime_id
        stored.hackatime_connected = True
        stored.hackatime_token = sealed
        stored.save(update_fields=["hackatime_user_id", "hackatime_connected", "hackatime_token"])
        audit.record("accounts.hackatime_connect", actor=stored.user, subject=stored.user, target=stored, details={})
    return True


def drop_token(profile):
    """For a token Hackatime rejected (the lead's later code calls it): under the Profile row lock set hackatime_token = ""
    and hackatime_connected = False, keep hackatime_user_id (so one Hackatime account still backs only one person),
    audit profile.hackatime_token_dropped with details={}; returns whether anything changed. Do not revoke."""
    with transaction.atomic():
        stored = Profile.objects.select_for_update().select_related("user").get(pk=profile.pk)
        if not stored.hackatime_token and not stored.hackatime_connected:
            return False
        stored.hackatime_token = ""
        stored.hackatime_connected = False
        stored.save(update_fields=["hackatime_token", "hackatime_connected"])
        audit.record("profile.hackatime_token_dropped", actor=stored.user, subject=stored.user, target=stored, details={})
    return True


def clean_name(value):
    """A Hackatime project name as typed, trimmed, or None when it cannot be one: 1 to 100 characters, nothing unprintable (no control characters or line
    breaks), and no comma (the API takes a comma separated list, so such a name could never be asked for exactly)."""
    name = value.strip() if isinstance(value, str) else ""
    return name if 0 < len(name) <= NAME_MAX_LENGTH and name.isprintable() and "," not in name else None


def stamp(moment):
    """A datetime as an explicit UTC ISO 8601 timestamp (research 3.4: how a bare timestamp is read is unknown, so always say Z)."""
    return moment.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


@sensitive_variables("token")
def project_seconds(token, name, start, end):
    """The seconds Hackatime has recorded for the project called `name` between `start` and `end` (datetimes), from
    GET api/v1/authenticated/projects?projects=NAME&start=&end=&include_archived=true. Nothing else of the answer is kept. ASSUMED (research 3.3 and 3.4,
    from the docs and the source, never run live): the body is a JSON object with a `projects` list of objects with a `name` and a `total_seconds` (a
    number), the name is matched exactly, and a project with no time in the window is simply missing (so 0). A bad name, a body in another shape, a
    negative, boolean or huge number, or more seconds than the window is long (so the window was ignored), raises."""
    cleaned = clean_name(name)
    if cleaned is None or cleaned != name:
        raise ValueError
    response = client().get("api/v1/authenticated/projects", token=token, params={
        "projects": name, "start": stamp(start), "end": stamp(end), "include_archived": "true"})
    response.raise_for_status()
    rows = response.json()["projects"]
    if not isinstance(rows, list):
        raise ValueError
    found = [row["total_seconds"] for row in rows if row["name"] == name]
    if not found:
        return 0
    seconds = found[0]
    if isinstance(seconds, bool) or not isinstance(seconds, (int, float)) or not 0 <= seconds <= MAX_SECONDS:
        raise ValueError
    if seconds > (end - start).total_seconds():                    # a window cannot hold more time than it is long: Hackatime ignored start and end
        raise ValueError
    return int(seconds)


def check_counts(seconds, checked_at, since, now):
    """Whether a stored check may back a hand-in while hours are required: at least MIN_SECONDS, made after `since` (when the project started, or was
    last handed in, so an old check cannot carry over to a later round) and no more than FRESH_FOR ago. Nothing stored (None) never counts."""
    return bool(seconds and seconds >= MIN_SECONDS and checked_at and since < checked_at <= now and now - checked_at <= FRESH_FOR)


@sensitive_variables("token")
def seconds_of(request, expected_id, name, start, end):
    """The seconds for one Hackatime project of the connection the person has just made, or None when anything at all went wrong (a refusal, a stale or
    forged state, a bad code, no network, an answer in a shape we do not know, or a Hackatime account that is not the one they connected: their
    `expected_id`). Like identity_of, a token that was handed over is revoked here whatever happened, and never leaves this function."""
    try:
        token = client().authorize_access_token(request)
    except Exception:
        return None
    try:
        if read_identity(token)[0] != expected_id:
            return None
        return project_seconds(token, name, start, end)
    except Exception:
        return None
    finally:
        revoke(token)
