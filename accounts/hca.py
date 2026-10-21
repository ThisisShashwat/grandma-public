"""Sign in with Hack Club (Hack Club Auth, OpenID Connect). The only module that knows the library (Authlib's Django client). The facts it
rests on and the reasons for each choice: docs/research/hackatime-and-hca.md.

WRITTEN DISABLED, for the owner to review before he enables it: nothing here runs unless the HCA_LOGIN admin setting is on AND HCA_CLIENT_ID and
HCA_CLIENT_SECRET are in the environment (`enabled`), and the library is only set up the first time it is needed.

A first Hack Club sign-in CREATES an account with an unusable password (never staff, never superuser) and attaches its Slack ID to the Profile.
The gate (ysws_eligible is True) is checked at first login only: returning participants are never polled or re-checked, so aging out mid-program
does not lock them out. It does not apply to a Slack ID listed in STAFF_SLACK_IDS (adult staff are not ysws_eligible and must still become admins). A returning sign-in finds the account by `hca_sub` and signs in. Staff and superusers may sign in this way; the admin itself
is gated separately (accounts/admin_gate.py). Hack Club is asked for five scopes (openid, profile, slack_id, verification_status, email) and we keep five fields (owner, 2026-10-07: the display name comes from Hack Club, FIRST NAME ONLY: `given_name` or else `nickname`, never the family name or the full name, and only if it passes the display name rules; the question in /welcome/ is skipped then): the stable `sub` id, the Slack ID and the
email (both private, never shown on a public page) and the time of the last sign-in. The email is kept current on every
sign-in; a missing or malformed one never blocks anything and is never invented. The tokens and the id token are read in memory and dropped: never stored, never logged, never put in the session.
"""
import hashlib
import re

from authlib.integrations.django_client import OAuth
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.urls import reverse
from django.utils import timezone

from accounts import identity
from accounts.models import Profile
from accounts.slack import is_member_id
from accounts.validators import validate_display_name
from audit import services as audit

NAME = "hackclub"
SCOPE = "openid profile slack_id verification_status email"
TIMEOUT_SECONDS = 5
CLAIMS = ("sub", "slack_id", "verification_status", "ysws_eligible", "email", "given_name", "nickname", "family_name", "name", "birthdate", "address")
SUB_MAX_LENGTH = 100
EMAIL_MAX_LENGTH = 254
EMAIL_SHAPE = re.compile(r"[^@\s]+@[^@\s]+")

oauth = OAuth()


def enabled(cfg):
    """Is Sign in with Hack Club on? `cfg` is pages.live.live()."""
    return bool(cfg.HCA_LOGIN and settings.HCA_CLIENT_ID and settings.HCA_CLIENT_SECRET)


def scope():
    """What Hack Club is asked for: the usual five, plus birthdate and address only when the identity capture is on (accounts/identity.py: it needs HQ to have
    approved those scopes for this app, or Hack Club would refuse every sign-in)."""
    return SCOPE + (" birthdate address" if identity.enabled() else "")


def client():
    """The Hack Club app, registered on first use from the settings (importing this module with no credentials does nothing). Authlib reads the
    discovery document, makes the state, the nonce and the PKCE verifier, keeps them in the session and checks the id token."""
    return oauth.create_client(NAME) or oauth.register(
        NAME, client_id=settings.HCA_CLIENT_ID, client_secret=settings.HCA_CLIENT_SECRET,
        server_metadata_url=f"{settings.HCA_ISSUER.rstrip('/')}/.well-known/openid-configuration",
        client_kwargs={"scope": scope(), "code_challenge_method": "S256", "default_timeout": TIMEOUT_SECONDS})


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
    """The five claims we use from the sign-in the person has just finished, or None when anything at all went wrong (a refusal at Hack Club, a
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


def clean_email(value):
    """The `email` claim made fit to keep (stripped, lowercased), or "" for anything else: not a string, over 254 characters, not exactly one @ with
    something on both sides, or whitespace inside. Never an error and never invented: a missing address blocks nothing."""
    if not isinstance(value, str):
        return ""
    email = value.strip().lower()
    return email if len(email) <= EMAIL_MAX_LENGTH and EMAIL_SHAPE.fullmatch(email) else ""


def clean_first_name(userinfo):
    """The display name to start an account with: the first name Hack Club gave (`given_name`, else `nickname`), or "" when there is none or it would
    not do as a display name (the shape rules only: it is shown to other people, so no markup or odd characters). It is NOT checked for rude words (owner,
    2026-10-07): Hack Club supplied it as the person's own name, and real names such as Wang or Dick must never be refused. Never the family name, never invented."""
    for key in ("given_name", "nickname"):
        value = userinfo.get(key)
        if isinstance(value, str) and value.strip():
            name = " ".join(value.split())
            try:
                validate_display_name(name)
            except ValidationError:
                return ""
            return name
    return ""


def may_sign_in(user):
    """Active users may sign in (staff and superusers included; the admin is gated separately, accounts/admin_gate.py)."""
    return bool(user.is_active)


def username_for(sub):
    """Deterministic username derived from sub and nothing else."""
    return "hca_" + hashlib.sha256(sub.encode()).hexdigest()[:32]


def keep_identity(profile, userinfo):
    """Refresh the encrypted identity from this sign-in (only with an encryption key, and when Hack Club sent something usable); returns whether it changed.
    The caller saves the Profile. A key problem never blocks a sign-in: it is skipped."""
    if not identity.stores():
        return False
    data = identity.clean(userinfo)
    if not data:
        return False
    try:
        sealed = identity.seal(data)
        if identity.unseal(profile.identity) == data:
            return False
    except identity.Unreadable:
        if not profile.identity:
            return False
        sealed = identity.seal(data)           # an old unreadable value (a retired key) is replaced by the fresh one
    profile.identity = sealed
    return True


def is_listed_staff(userinfo):
    """Is the Slack ID of this sign-in (the `slack_id` claim, verified by Hack Club) exactly one of the environment list STAFF_SLACK_IDS?"""
    slack_id = (userinfo or {}).get("slack_id")
    return bool(settings.STAFF_SLACK_IDS) and isinstance(slack_id, str) and slack_id in settings.STAFF_SLACK_IDS


def grant_staff(profile, userinfo):
    """The only way an admin is made: a Hack Club sign-in whose Slack ID (verified by Hack Club, in the `slack_id` claim) is in the environment list
    STAFF_SLACK_IDS becomes staff, superuser and a beta member, at the first sign-in and at every later one. Nobody else is ever promoted here, an empty
    list promotes nobody, and nothing is ever taken away (untick by hand in the admin). The audit entry names the fields, never the Slack ID."""
    if not is_listed_staff(userinfo):
        return
    user = profile.user
    changed = [name for name, have in (("is_staff", user.is_staff), ("is_superuser", user.is_superuser), ("beta_access", profile.beta_access)) if not have]
    if not changed:
        return
    user.is_staff = user.is_superuser = True
    profile.beta_access = True
    user.save(update_fields=["is_staff", "is_superuser"])
    profile.save(update_fields=["beta_access"])
    audit.record("accounts.staff_grant", actor=user, subject=user, target=profile, details={"fields": changed})


def sign_in(profile, email="", userinfo=None):
    """Sign in a returning person: check they may sign in, update the check time, keep the email current and record the login. A present email
    that differs from the stored one replaces it (they may change it at Hack Club; `hca_sub` stays the identity) and is audited as a profile
    update naming the field only, never the address. A missing one leaves the stored one alone."""
    if not may_sign_in(profile.user):
        return None, "no_account"
    changed = ["email"] if email and email != profile.email else []
    if changed:
        profile.email = email
    name = "" if profile.display_name else clean_first_name(userinfo or {})       # a blank name is filled from Hack Club; a name they have is never touched
    if name:
        profile.display_name = name
        changed.append("display_name")
    profile.hca_checked_at = timezone.now()
    new_identity = keep_identity(profile, userinfo or {})
    profile.save(update_fields=["hca_checked_at", *changed, *(["identity"] if new_identity else [])])
    if changed:
        audit.record("profile.update", actor=profile.user, subject=profile.user, target=profile, details={"fields": changed})
    grant_staff(profile, userinfo)
    audit.record("accounts.hca_login", actor=profile.user, subject=profile.user, target=profile, details={"created": False})
    return profile, None


def create(sub, slack_id, email="", display_name="", userinfo=None):
    """Create a user and profile for a first-time Hack Club sign-in, and record the login."""
    # create_user without a password creates an account with an unusable password on purpose.
    user = get_user_model().objects.create_user(username=username_for(sub))
    profile = Profile.objects.create(
        user=user,
        hca_sub=sub,
        slack_id=slack_id,
        email=email,
        display_name=display_name,
        hca_checked_at=timezone.now(),
    )
    if keep_identity(profile, userinfo or {}):
        profile.save(update_fields=["identity"])
    grant_staff(profile, {"slack_id": slack_id})
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

    email = clean_email(userinfo.get("email"))
    with transaction.atomic():
        profile = Profile.objects.select_for_update().select_related("user").filter(hca_sub=sub).first()
        if profile is not None:
            return sign_in(profile, email, userinfo)

        ok, reason = check(userinfo, require_eligible and not is_listed_staff(userinfo))        # listed staff are adults: the age gate never refuses them
        if not ok:
            return None, reason

        slack_id = userinfo.get("slack_id")
        try:
            with transaction.atomic():
                profile = create(sub, slack_id, email, clean_first_name(userinfo), userinfo)
                return profile, None
        except IntegrityError:
            profile = Profile.objects.select_for_update().select_related("user").filter(hca_sub=sub).first()
            if profile is not None:
                return sign_in(profile, email, userinfo)
            return None, "no_account"
