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
