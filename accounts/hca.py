"""Sign in with Hack Club (Hack Club Auth, OpenID Connect). The only module that knows the library (Authlib's Django client). The facts it
rests on and the reasons for each choice: docs/research/hackatime-and-hca.md.

WRITTEN DISABLED, for the owner to review before he enables it: nothing here runs unless the HCA_LOGIN admin setting is on AND HCA_CLIENT_ID and
HCA_CLIENT_SECRET are in the environment (`enabled`), and the library is only set up the first time it is needed.

It NEVER creates an account (the owner has not decided: research section 6). The first Hack Club sign-in only LINKS to an account staff already
made, matched by the Slack ID, and refuses anyone else (`identify`). Hack Club is asked for three things (openid, slack_id, verification_status)
and we keep two: the stable `sub` id and the time of the last check. The tokens and the id token are read in memory and dropped: never stored,
never logged, never put in the session.
"""
from authlib.integrations.django_client import OAuth
from django.conf import settings
from django.db import transaction
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
    """The redirect to Hack Club, with the state, nonce and PKCE challenge saved in the session."""
    return client().authorize_redirect(request, redirect_uri())


def userinfo_of(request):
    """The four claims we use from the sign-in the person has just finished, or None when anything at all went wrong (a refusal at Hack Club, a
    stale or forged state, a bad code, a failed signature or nonce, no id token, no network). The token is dropped here."""
    try:
        userinfo = client().authorize_access_token(request)["userinfo"]
        return {key: userinfo.get(key) for key in CLAIMS}
    except Exception:
        return None


def check(userinfo, require_eligible):
    """Whether this sign-in may go on: (True, None) or (False, reason) with reason one of pending, not_eligible, not_verified, no_slack_id.
    Required eligibility means a verified identity that Hack Club says may join (ysws_eligible is true). The Slack ID is always needed: it is
    how the account is found."""
    if require_eligible:
        status = userinfo.get("verification_status")
        if status == "pending":
            return False, "pending"
        if status == "ineligible":
            return False, "not_eligible"
        if status != "verified":
            return False, "not_verified"
        if userinfo.get("ysws_eligible") is not True:
            return False, "not_eligible"
    slack_id = userinfo.get("slack_id")
    if not isinstance(slack_id, str) or not is_member_id(slack_id):
        return False, "no_slack_id"
    return True, None


def identify(userinfo):
    """The Profile to sign in, or None to refuse. Matched by the stored `sub`; otherwise by the Slack ID (exactly, and only when it is shaped
    like one), and then the `sub` is LINKED to that Profile for good. Refused: no match, an inactive user, a Profile already linked to another
    `sub`. On success it stamps the check time and writes the audit entry in the same transaction, with the Profile row locked."""
    sub, slack_id = userinfo.get("sub"), userinfo.get("slack_id")
    if not isinstance(sub, str) or not 0 < len(sub) <= SUB_MAX_LENGTH:
        return None
    with transaction.atomic():
        profiles = Profile.objects.select_for_update().select_related("user")
        profile = profiles.filter(hca_sub=sub).first()
        linking = profile is None
        if linking and isinstance(slack_id, str) and is_member_id(slack_id):
            profile = profiles.filter(slack_id=slack_id).first()
        if profile is None or not profile.user.is_active or (linking and profile.hca_sub):
            return None
        profile.hca_sub, profile.hca_checked_at = sub, timezone.now()
        profile.save(update_fields=["hca_sub", "hca_checked_at"])
        audit.record("accounts.hca_login", actor=profile.user, subject=profile.user, target=profile, details={"linked": linking})
    return profile
