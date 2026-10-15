from django.db import transaction
from django.views.decorators.debug import sensitive_variables

from accounts import hackatime
from accounts.models import Profile
from audit import services as audit


def profile_of(user):
    """The user's Profile, made empty on first use."""
    return Profile.objects.get_or_create(user=user)[0]


def request_profile(request):
    """The signed in person's Profile, read once per request and kept on the request (the gates, the page and the dialogue's store all ask for it: each
    used to cost a query). Only for reading at the edges of a request; a service that changes a Profile locks and reads its own row."""
    if getattr(request, "_profile", None) is None:
        request._profile = profile_of(request.user)
    return request._profile


def set_beta_access(profile, granted, *, by):
    """Give (True) or take away (False) a person's beta access and record it. It compares with what is stored now, so a repeat or a stale
    admin page writes nothing. Returns whether anything changed. `by` is the staff member."""
    with transaction.atomic():
        stored = Profile.objects.select_for_update().select_related("user").get(pk=profile.pk)
        if stored.beta_access == granted:
            return False
        stored.beta_access = profile.beta_access = granted
        stored.save(update_fields=["beta_access"])
        audit.record("profile.beta_access", actor=by, subject=stored.user, target=stored, details={"beta_access": granted})
    return True


def send_back_to_onboarding(profile, *, by):
    """Staff put a person back at the start of /welcome/ (a step was added, or a connection was wiped): `onboarded_at` and `tutorial_done_at` are cleared and
    everything they answered is kept, so the boxes come back filled in. It compares with what is stored now, so a repeat writes nothing. Recorded with no
    details. Returns whether anything changed. `by` is the staff member."""
    with transaction.atomic():
        stored = Profile.objects.select_for_update().select_related("user").get(pk=profile.pk)
        if stored.onboarded_at is None and stored.tutorial_done_at is None:
            return False
        stored.onboarded_at = stored.tutorial_done_at = profile.onboarded_at = profile.tutorial_done_at = None
        stored.save(update_fields=["onboarded_at", "tutorial_done_at"])
        audit.record("profile.onboarding_reset", actor=by, subject=stored.user, target=stored, details={})
    return True


@sensitive_variables()
def unlink_hackatime(profile, *, by):
    """Staff clear a person's Hackatime link (the wrong account, or one that was banned): the id, the connected flag
    and the stored token, so they can connect again. Recorded, with no details. Revokes the old token best effort
    after the transaction commits. Returns whether anything changed. `by` is the staff member."""
    with transaction.atomic():
        stored = Profile.objects.select_for_update().select_related("user").get(pk=profile.pk)
        if stored.hackatime_user_id is None and not stored.hackatime_connected and not stored.hackatime_token:
            return False
        old_token = stored.hackatime_token
        stored.hackatime_user_id, stored.hackatime_connected, stored.hackatime_token = None, False, ""
        stored.save(update_fields=["hackatime_user_id", "hackatime_connected", "hackatime_token"])
        audit.record("profile.hackatime_unlink", actor=by, subject=stored.user, target=stored, details={})
    if old_token:
        try:
            plain = hackatime.unseal(old_token)
            hackatime.revoke({"access_token": plain})
        except Exception:
            pass
    return True
