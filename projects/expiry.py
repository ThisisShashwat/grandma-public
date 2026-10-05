"""A `dealing` project nobody came back to expires: it becomes `abandoned`, which frees its person to start another (the same status staff set with
the admin action). The window is the admin setting DEALING_EXPIRY_DAYS.

"Last activity" is `created_at`, the moment the hand was dealt: the Project model has no modified timestamp, and a re-deal changes the hand, not a date.
Only a hand that was never confirmed (`started_at` empty) can expire. A building project that was re-dealt is `dealing` again too, but it has real
work behind it, and a `building` project is never touched.

Two callers: Talk to Grandma, for the person who opens it (`expire_stale(user)`), and the `expire_dealing` command for everybody, for a cron job."""
from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from accounts.models import Profile
from audit import services as audit
from pages.live import live
from projects import rules
from projects.models import Project


def is_stale(project, days, now):
    """The decision: a project whose hand was dealt more than `days` days ago and never confirmed."""
    return project.status == rules.DEALING and project.started_at is None and now - project.created_at > timedelta(days=days)


def expire_stale(user=None, *, days=None, now=None):
    """Abandon the stale `dealing` projects of one person, or of everybody. `days` is DEALING_EXPIRY_DAYS unless given (a caller that already
    read the settings passes it). Returns how many expired."""
    days = live().DEALING_EXPIRY_DAYS if days is None else days
    now = now or timezone.now()
    candidates = Project.objects.filter(status=rules.DEALING, started_at__isnull=True).select_related("user")
    if user is not None:
        candidates = candidates.filter(user=user)
    return sum(expire(project, days, now) for project in candidates if is_stale(project, days, now))


def expire(candidate, days, now):
    """Abandon one project, if it is still stale once locked (its person may have confirmed the hand a moment ago). 1 if it expired, else 0."""
    with transaction.atomic():
        Profile.objects.select_for_update().filter(user_id=candidate.user_id).first()      # the lock order of projects/services.py: the person, then the project
        project = Project.objects.select_for_update().filter(pk=candidate.pk).first()
        if project is None or not is_stale(project, days, now):
            return 0
        project.status = rules.ABANDONED
        project.save(update_fields=["status"])
        audit.record("project.expire", subject=candidate.user, target=project, details={"project": project.pk, "days": days})
    return 1
