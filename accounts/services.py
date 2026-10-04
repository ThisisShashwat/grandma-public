from django.db import transaction

from accounts.models import Profile
from audit import services as audit


def profile_of(user):
    """The user's Profile, made empty on first use."""
    return Profile.objects.get_or_create(user=user)[0]


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


def unlink_hca(profile, *, by):
    """Staff clear a person's Hack Club link (a wrong identity, or a new one): the `sub` and the time of its last check, so the next sign-in links again.
    Recorded, with no details (nothing from Hack Club goes in the log). Returns whether anything changed. `by` is the staff member."""
    with transaction.atomic():
        stored = Profile.objects.select_for_update().select_related("user").get(pk=profile.pk)
        if stored.hca_sub is None and stored.hca_checked_at is None:
            return False
        stored.hca_sub = stored.hca_checked_at = None
        stored.save(update_fields=["hca_sub", "hca_checked_at"])
        audit.record("profile.hca_unlink", actor=by, subject=stored.user, target=stored, details={})
    return True


def unlink_hackatime(profile, *, by):
    """Staff clear a person's Hackatime link (the wrong account, or one that was banned): the id and the connected flag, so they can connect again.
    Recorded, with no details. Returns whether anything changed. `by` is the staff member."""
    with transaction.atomic():
        stored = Profile.objects.select_for_update().select_related("user").get(pk=profile.pk)
        if stored.hackatime_user_id is None and not stored.hackatime_connected:
            return False
        stored.hackatime_user_id, stored.hackatime_connected = None, False
        stored.save(update_fields=["hackatime_user_id", "hackatime_connected"])
        audit.record("profile.hackatime_unlink", actor=by, subject=stored.user, target=stored, details={})
    return True
