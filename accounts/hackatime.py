"""Connecting a Hackatime account (OAuth2, plain: not OpenID Connect). The only module that knows the library (Authlib's Django client). The facts it
rests on and the reasons for each choice: docs/research/hackatime-and-hca.md (section 3 and 5).

WRITTEN DISABLED, for the owner to review before he enables it: nothing here runs unless the HACKATIME_ENABLED admin setting is on, HACKATIME_CLIENT_ID
and HACKATIME_CLIENT_SECRET are in the environment, and HACKATIME_TOKEN_KEYS is non-empty (`enabled`), and the library is only set up the first time
it is needed. Until then the Hackatime step of onboarding is the old greyed-out button (accounts/script.py).

Hackatime is asked for two scopes (profile read: `profile` cannot be left out) and we keep the person's Hackatime user id and the access token
encrypted at rest (HACKATIME_TOKEN_KEYS). Never logged, never shown, never in the admin, never in the session. The answer of that call carries emails:
it is read in memory and dropped, nothing but the id and the Slack ID (which is only compared with the Profile's, never stored) leaves `read_identity`.

The stored token reads the time server side (`read`, `list_projects`, `total_seconds`). When checking hours from the submit note, the person picks
projects and their time is read without any redirect to Hackatime. When Hackatime rejects the token, they are asked to reconnect.
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
NAME_MAX_LENGTH = 100                      # the longest Hackatime project name we ask about (the per name limit is enforced by clean_name)
MAX_SECONDS = 2**31 - 1                    # what the database column holds
MIN_SECONDS = 600                          # when hours are required: a ten-minute floor, so one stray heartbeat is not "work" (code, not a setting)
FRESH_FOR = timedelta(hours=24)            # when hours are required: a check older than this is made again
MAX_PROJECTS = 10                          # the most Hackatime projects one hand-in may count


class TokenUnreadable(Exception):
    """The stored token is empty, corrupted, or cannot be decrypted."""


class Reconnect(Exception):
    """There is no usable token: the person must connect again."""


class Unreadable(Exception):
    """Hackatime would not show their time: banned, down, an answer in a shape we do not know."""


class Connection(NamedTuple):
    """A verified Hackatime identity and its sealed access token."""

    hackatime_id: str
    slack_id: str | None
    sealed: str


oauth = OAuth()


def enabled(cfg):
    """Is connecting Hackatime on? `cfg` is pages.live.live()."""
    return bool(cfg.HACKATIME_ENABLED and settings.HACKATIME_CLIENT_ID and settings.HACKATIME_CLIENT_SECRET and getattr(settings, "HACKATIME_TOKEN_KEYS", None))


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


@sensitive_variables()
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


@sensitive_variables()
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


@sensitive_variables()
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


@sensitive_variables()
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
    """For a token Hackatime rejected (`read` calls it when the probe also answers 401): under the Profile row lock set hackatime_token = ""
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
def read(profile, path, params=None):
    """Call client().get(path, token=token_of(profile), params=params) and return the parsed JSON body (a dict).
    Rules, with no retry loop:
    - no token (token_of is None) raises Reconnect;
    - a network error, a non-2xx status other than 401, a body that is not JSON or not a dict raises Unreadable;
    - a 401 means the token may have been rejected: make ONE probe GET api/v1/authenticated/me with the same token:
      only when the probe itself answers 401 is the token dead, so call drop_token(profile) and raise Reconnect;
      any other outcome of the probe (2xx: the account is banned or similar, an exception, 429, 5xx, anything else) raises Unreadable and keeps the token."""
    token = token_of(profile)
    if token is None:
        raise Reconnect
    try:
        response = client().get(path, token=token, params=params)
    except Exception:
        raise Unreadable from None

    status = getattr(response, "status_code", None)
    if status == 401:
        try:
            probe = getattr(client().get("api/v1/authenticated/me", token=token), "status_code", None)
        except Exception:
            probe = None
        if probe != 401:
            raise Unreadable
        drop_token(profile)
        raise Reconnect

    if status is None or not (200 <= status < 300):
        raise Unreadable

    try:
        body = response.json()
    except Exception:
        raise Unreadable from None

    if not isinstance(body, dict):
        raise Unreadable

    return body


@sensitive_variables("token")
def list_projects(profile, start, end):
    """Every Hackatime project that has recorded time in the window [start, end].
    Calls GET api/v1/authenticated/projects with params start, end, include_archived="true".
    Returns a list of (name, seconds) tuples sorted by seconds descending then name, capped at 200 rows.
    A row without a valid name passing clean_name unchanged, or without valid total_seconds (not bool, 0 <= s <= MAX_SECONDS,
    not more than the window is long), is skipped. A body without a projects list raises Unreadable."""
    params = {
        "start": stamp(start),
        "end": stamp(end),
        "include_archived": "true",
    }
    body = read(profile, "api/v1/authenticated/projects", params=params)
    rows = body.get("projects")
    if not isinstance(rows, list):
        raise Unreadable

    window_seconds = (end - start).total_seconds()
    result = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        name = row.get("name")
        cleaned = clean_name(name)
        if cleaned is None or cleaned != name:
            continue
        seconds = row.get("total_seconds")
        if isinstance(seconds, bool) or not isinstance(seconds, (int, float)):
            continue
        if not (0 <= seconds <= MAX_SECONDS):
            continue
        if seconds > window_seconds:
            continue
        result.append((name, int(seconds)))

    result.sort(key=lambda item: (-item[1], item[0]))
    return result[:200]


@sensitive_variables("token")
def total_seconds(profile, names, start, end):
    """The combined seconds of all names in the window without double counting overlaps, from
    GET api/v1/users/my/stats with total_seconds="true", filter_by_project, start_date and end_date.

    ASSUMED (documented from Hackatime's source, never run live): the endpoint accepts the OAuth read token,
    my means its owner, the window is half open, ISO 8601 with Z is accepted, a bad date answers 400.

    names must be 1 to MAX_PROJECTS items, each passing clean_name unchanged, with no duplicates, else ValueError.
    N must be a number (not bool), 0 <= N <= MAX_SECONDS, and not more than the window is long, else Unreadable.
    Returns int(N)."""
    if not isinstance(names, (list, tuple)) or not (1 <= len(names) <= MAX_PROJECTS):
        raise ValueError
    if len(set(names)) != len(names):
        raise ValueError
    for name in names:
        cleaned = clean_name(name)
        if cleaned is None or cleaned != name:
            raise ValueError

    params = {
        "total_seconds": "true",
        "filter_by_project": ",".join(names),
        "start_date": stamp(start),
        "end_date": stamp(end),
    }
    body = read(profile, "api/v1/users/my/stats", params=params)
    if "total_seconds" not in body:
        raise Unreadable

    n = body["total_seconds"]
    if isinstance(n, bool) or not isinstance(n, (int, float)):
        raise Unreadable
    if not (0 <= n <= MAX_SECONDS):
        raise Unreadable
    window_seconds = (end - start).total_seconds()
    if n > window_seconds:
        raise Unreadable

    return int(n)


def window(project, now):
    """(project.started_at, now). The window starts when the person kept their demands (started_at, set when the project became building), not before, so work done before they spoke to Grandma never counts."""
    return project.started_at, now


def check_counts(seconds, checked_at, since, now):
    """Whether a stored check may back a hand-in while hours are required: at least MIN_SECONDS, made after `since` (when the project started, or was
    last handed in, so an old check cannot carry over to a later round) and no more than FRESH_FOR ago. Nothing stored (None) never counts."""
    return bool(seconds and seconds >= MIN_SECONDS and checked_at and since < checked_at <= now and now - checked_at <= FRESH_FOR)
