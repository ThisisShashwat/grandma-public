"""Sign in with Hack Club (Hack Club Auth, OpenID Connect). The only module that knows the library (Authlib's Django client). The facts it
rests on and the reasons for each choice: docs/research/hackatime-and-hca.md.

WRITTEN DISABLED, for the owner to review before he enables it: nothing here runs unless the HCA_LOGIN admin setting is on AND HCA_CLIENT_ID and
HCA_CLIENT_SECRET are in the environment (`enabled`), and the library is only set up the first time it is needed.

A first Hack Club sign-in CREATES an account with an unusable password (never staff, never superuser) and attaches its Slack ID to the Profile.
The gate (ysws_eligible is True) is checked at first login only: returning participants are never polled or re-checked, so aging out mid-program
does not lock them out. A returning sign-in finds the account by `hca_sub` and signs in. Staff and superusers may sign in this way; the admin itself
is gated separately (accounts/admin_gate.py). Hack Club is asked for three scopes (openid, slack_id, verification_status) and we keep two fields: the stable `sub` id and the time
of the last sign-in. The tokens and the id token are read in memory and dropped: never stored, never logged, never put in the session.
"""
import hashlib

from authlib.integrations.django_client import OAuth
from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.urls import reverse
from django.utils import timezone

from accounts.models import Profile
from accounts.slack import is_member_id
from audit import services as audit

NAME = "hackclub"
SCOPE = "openid slack_id verification_status"
TIMEOUT_SECONDS = 5
CLAIMS = ("sub", "slack_id", "verification_status", "ysws_eligible")
SUB_MAX_LENGTH = 100

oauth = OAuth()


def enabled(cfg):
    """Is Sign in with Hack Club on? `cfg` is pages.live.live()."""
    return bool(cfg.HCA_LOGIN and settings.HCA_CLIENT_ID and settings.HCA_CLIENT_SECRET)


def client():
    """The Hack Club app, registered on first use from the settings (importing this module with no credentials does nothing). Authlib reads the
    discovery document, makes the state, the nonce and the PKCE verifier, keeps them in the session and checks the id token."""
    return oauth.create_client(NAME) or oauth.register(
        NAME, client_id=settings.HCA_CLIENT_ID, client_secret=settings.HCA_CLIENT_SECRET,
        server_metadata_url=f"{settings.HCA_ISSUER.rstrip('/')}/.well-known/openid-configuration",
        client_kwargs={"scope": SCOPE, "code_challenge_method": "S256", "default_timeout": TIMEOUT_SECONDS})


def redirect_uri():
    return settings.SITE_URL.rstrip("/") + reverse("login_hackclub_callback")


def authorize_redirect(request):
    """The redirect to Hack Club, with the state, nonce and PKCE challenge saved in the session. `prompt=login` (documented by Hack Club, research 2.3)
    makes it ask the person to sign in again: logging out here cannot end their Hack Club session (it has no end_session_endpoint), so on a shared
    computer the next person would otherwise be signed in as the last one."""
    return client().authorize_redirect(request, redirect_uri(), prompt="login")


def claims_options():
    """What the id token must say on top of the library's own checks (signature, expiry, nonce, `azp`): the configured issuer (with or without a
    trailing slash), and OUR client id among its audience. Giving options replaces the library's default issuer check, so the issuer is here too."""
    issuer = settings.HCA_ISSUER.rstrip("/")
    return {"iss": {"essential": True, "values": [issuer, issuer + "/"]}, "aud": {"essential": True, "values": [settings.HCA_CLIENT_ID]}}


def userinfo_of(request):
    """The four claims we use from the sign-in the person has just finished, or None when anything at all went wrong (a refusal at Hack Club, a
    stale or forged state, a bad code, a failed signature, issuer, audience or nonce, no id token, no network). The token is dropped here."""
    try:
        userinfo = client().authorize_access_token(request, claims_options=claims_options())["userinfo"]
        return {key: userinfo.get(key) for key in CLAIMS}
    except Exception:
        return None


def check(userinfo, require_eligible):
    """Whether a first sign-in may proceed: (True, None) or (False, reason) with reason in not_eligible, no_slack_id.
    If require_eligible is on, ysws_eligible must be True (verification_status is not checked). The Slack ID must
    be a valid member ID string."""
    if require_eligible and userinfo.get("ysws_eligible") is not True:
        return False, "not_eligible"
    slack_id = userinfo.get("slack_id")
    if not isinstance(slack_id, str) or not is_member_id(slack_id):
        return False, "no_slack_id"
    return True, None


def may_sign_in(user):
    """Active users may sign in (staff and superusers included; the admin is gated separately, accounts/admin_gate.py)."""
    return bool(user.is_active)


def username_for(sub):
    """Deterministic username derived from sub and nothing else."""
    return "hca_" + hashlib.sha256(sub.encode()).hexdigest()[:32]


def sign_in(profile):
    """Sign in a returning person: check they may sign in, update the check time, and record the login."""
    if not may_sign_in(profile.user):
        return None, "no_account"
    profile.hca_checked_at = timezone.now()
    profile.save(update_fields=["hca_checked_at"])
    audit.record("accounts.hca_login", actor=profile.user, subject=profile.user, target=profile, details={"created": False})
    return profile, None


def create(sub, slack_id):
    """Create a user and profile for a first-time Hack Club sign-in, and record the login."""
    # create_user without a password creates an account with an unusable password on purpose.
    user = get_user_model().objects.create_user(username=username_for(sub))
    profile = Profile.objects.create(
        user=user,
        hca_sub=sub,
        slack_id=slack_id,
        hca_checked_at=timezone.now(),
    )
    audit.record("accounts.hca_login", actor=user, subject=user, target=profile, details={"created": True})
    return profile


def identify(userinfo, require_eligible):
    """The Profile to sign in or create, or (None, reason).
    Returns (Profile, None) on success, (None, reason) otherwise where reason is one of
    not_eligible, no_slack_id, no_account.
    Invalid or missing sub gives (None, 'no_account')."""
    sub = userinfo.get("sub")
    if not isinstance(sub, str) or not 0 < len(sub) <= SUB_MAX_LENGTH:
        return None, "no_account"

    with transaction.atomic():
        profile = Profile.objects.select_for_update().select_related("user").filter(hca_sub=sub).first()
        if profile is not None:
            return sign_in(profile)

        ok, reason = check(userinfo, require_eligible)
        if not ok:
            return None, reason

        slack_id = userinfo.get("slack_id")
        try:
            with transaction.atomic():
                profile = create(sub, slack_id)
                return profile, None
        except IntegrityError:
            profile = Profile.objects.select_for_update().select_related("user").filter(hca_sub=sub).first()
            if profile is not None:
                return sign_in(profile)
            return None, "no_account"
