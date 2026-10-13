"""The three answers a person may change after /welcome/ (the settings page, docs/accounts.md "The settings page"): display name, time zone, region.
Everything else on a Profile stays out of the person's reach."""
from django.db import transaction

from accounts.models import Profile
from accounts.onboarding import check
from audit import services as audit

EDITABLE = ("display_name", "timezone", "region")
REFUSED = "That doesn't sit right with my book, dear. Look the three boxes over and try again."


def update(user, answers):
    """Save the fields of `answers` (display_name, timezone, region: the settings form's cleaned data) that differ from what is stored, under the Profile's
    lock, and record ONE `profile.update` audit entry naming the fields, never the values. The model's rules and constraints are checked as onboarding checks
    them; a ValidationError means nothing was written. Returns the names of the fields that changed: empty means nothing was written and nothing recorded."""
    with transaction.atomic():
        stored = Profile.objects.select_for_update().get(user=user)
        changed = [key for key in EDITABLE if getattr(stored, key) != answers[key]]
        if not changed:
            return []
        for key in changed:
            setattr(stored, key, answers[key])
        check(stored)
        stored.save(update_fields=changed)
        audit.record("profile.update", actor=user, subject=user, target=stored, details={"fields": changed})
    return changed
