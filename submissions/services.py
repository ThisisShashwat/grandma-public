"""Everything that changes a submission, and the reads the pages need. Rules are in rules.py (pure); this layer applies them to the
database. Every change takes the same locks as projects and the ledger, in the same order: the person's Profile row first, then the
rows being changed, so two clicks on the same button cannot both win (SQLite is in IMMEDIATE mode, settings.py; on Postgres the row
locks do the work). The cookie handover writes the ledger only through ledger.services, under the key `submission:{id}`."""
from functools import partial

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from audit import services as audit
from ledger import services as ledger
from projects import rules as project_rules
from projects import services as project_services
from projects.models import Project
from submissions import notices, rules
from submissions.models import Submission

NOTHING_TO_SHIP = "You have nothing to hand in right now, dear. Only a project you are building."
CHECK_YOUR_HOURS = "Check your hours first, dear. I won't take it until Hackatime has shown me some time on this project. Use the Check my hours button on the note."
UNFIT_NOTES = "One of the notes you kept doesn't suit this kind of project, dear. Swap it with Change my demands on your project page. Stuck? Ask the staff in the Slack."
OWN_PROJECT = "You cannot review your own project. Ask another reviewer."
REVIEW_FIELDS = ("status", "approved_hours", "quality", "ribbon", "public_note", "internal_note", "reviewed_by", "reviewed_at", "cookies_awarded")


class AlreadyCollected(Exception):
    """The person has already been handed the result: the review is frozen (a correction is a ledger adjustment)."""


class NameTaken(Exception):
    """The Hackatime project name already backs another of this person's projects."""


def shipping_project(user):
    """The project this person could hand in now: the one they are building. None if there is none."""
    return Project.objects.filter(user=user, status=project_rules.BUILDING).first()


def fixing_project(user, project_id):
    """The person's own project that has changes requested, which they can fix and hand in again. None for any other id."""
    return Project.objects.filter(pk=project_id, user=user, status=project_rules.CHANGES_REQUESTED).first()


def sole_fixing_project(user):
    """The person's project with changes requested when there is exactly one (where /submit/ sends them), else None."""
    found = list(Project.objects.filter(user=user, status=project_rules.CHANGES_REQUESTED)[:2])
    return found[0] if len(found) == 1 else None


def latest_round(project):
    """The newest round this project has handed in (the one a fix starts from), or None."""
    return project.submissions.order_by("-round", "-id").first()


def ship_for(project):
    """What this project may hand in next (rules.next_round) given the rounds it has handed in so far."""
    return rules.next_round(list(project.submissions.values_list("round", "status")))


def locked_to_hand_in(user, project_id):
    """The project row, locked, that a hand-in is for: the one being built, or with an id the person's own project with changes requested."""
    if project_id is None:
        return project_services.locked_project(user, project_rules.BUILDING)
    return Project.objects.select_for_update().filter(pk=project_id, user=user, status=project_rules.CHANGES_REQUESTED).first()


def waiting(user):
    """The oldest reviewed submission of this person that Grandma has not yet handed over, or None."""
    return (Submission.objects.filter(project__user=user, status__in=rules.REVIEWED, claimed_at__isnull=True)
            .select_related("project").order_by("reviewed_at", "id").first())


def check_notes(project):
    """Refuses a hand-in that holds a kept note which does not suit the project's category and subcategory. An edit already drops such notes,
    so this only catches what staff changed in the admin (a project's kind, a demand's exclusions). Reads only."""
    if project_services.unfit_kept(project).exists():
        raise ValidationError(UNFIT_NOTES)


def check_hours(project, *, hackatime_required=False, hours_check=None):
    """The hours refusals of a hand-in, as a ValidationError with a sentence: `hours_check` (hours.require_fresh over this project) and, while
    hours are required, a check that found some. Reads only: submit runs it on the locked, re-read project, the form on the loaded one
    before it decodes the screenshot."""
    if hours_check:
        hours_check(project)
    if hackatime_required and not project.tracked_seconds:
        raise ValidationError(CHECK_YOUR_HOURS)


@transaction.atomic
def submit(user, *, project_id=None, hackatime_required=False, hours_check=None, repo_url, playable_url, description, screenshot, recording_url, declarations, ai_declaration_text):
    """Hand in a project. Without `project_id`: the person's project in building, as round 1. With it: the person's own project with
    changes requested, as the next round (a reviewer already granted it, whatever MAX_ROUNDS says now). The project becomes `in_review`.
    ValidationError (a sentence for the person) when there is nothing to hand in, no round left, or a kept note does not suit the project's
    category and subcategory (check_notes).
    One at a time: a second click finds the project already in review. The Hackatime hours the project has been checked for (and the name they are
    under) are copied onto the submission as they are now, and stay as they were; `hackatime_required` (hackatime.required(cfg), read once per request)
    refuses a project with no checked hours, which is a ValidationError too. `hours_check`, when given, is called with the locked, re-read project (so
    a check made in a second tab cannot slip past it) and raises ValidationError when the stored check is too short, too old or from before the start;
    nothing is saved then."""
    project_services.lock_person(user)
    locked = locked_to_hand_in(user, project_id)
    if locked is None:
        raise ValidationError(NOTHING_TO_SHIP)
    project = Project.objects.get(pk=locked.pk)
    ship = ship_for(project)
    if ship.problem:
        raise ValidationError(ship.problem)
    check_notes(project)
    check_hours(project, hackatime_required=hackatime_required, hours_check=hours_check)
    submission = Submission(project=project, round=ship.number, repo_url=repo_url, playable_url=playable_url, description=description,
                            screenshot=screenshot, recording_url=recording_url, declarations=declarations, ai_declaration_text=ai_declaration_text,
                            hackatime_projects=list(project.tracked_names), tracked_seconds=project.tracked_seconds, tracked_at=project.tracked_at)
    submission.full_clean()
    submission.save()
    project.status = project_rules.IN_REVIEW
    project.save(update_fields=["status"])
    audit.record(
        "submission.submit",
        actor=user,
        subject=user,
        target=submission,
        details={
            "project": project.id,
            "round": submission.round,
            "project_name": project.name,
            "category": project.category_id,
            "subcategory": project.subcategory_id,
            "kept": [d.id for d in project_services.kept_demands(project)],
            "hand": list(project.hand),
            "redeals_used": project.redeals_used,
        },
    )
    return submission


@transaction.atomic
def record_hours(user, project_id, names, seconds, now=None):
    """Keep what Hackatime said for this project: the names it was asked about, the seconds, and when. Only the person's own project that can be handed in
    (being built, or with changes requested), found by id under the locks; a second check replaces the first. NameTaken (nothing changes) when any other
    project of theirs already has one of these names: one Hackatime project backs only one of their projects. An abandoned or a rejected project no
    longer backs anything, so its names may be used again; approved, handed in, in review, changes requested and building ones still hold theirs.
    Returns the project, None when it is not theirs to check. The audit entry says only whether any time was found and how many projects were
    checked: never the seconds or the names."""
    project_services.lock_person(user)
    project = Project.objects.select_for_update().filter(pk=project_id, user=user, status__in=(project_rules.BUILDING, project_rules.CHANGES_REQUESTED)).first()
    if project is None:
        return None
    names_set = set(names)
    for other in Project.objects.filter(user=user).exclude(pk=project.pk).exclude(status__in=(project_rules.ABANDONED, project_rules.REJECTED)):
        if any(n in names_set for n in other.tracked_names):
            raise NameTaken
    project.tracked_names = list(names)
    project.tracked_seconds = seconds
    project.tracked_at = now or timezone.now()
    project.save(update_fields=["tracked_names", "tracked_seconds", "tracked_at"])
    audit.record("project.hackatime_check", actor=user, subject=user, target=project, details={"has_hours": seconds > 0, "projects": len(names)})
    return project


def tiers_of(project):
    """The tiers of the demands this project kept: what the payout formula wants."""
    return [demand.tier for demand in project_services.kept_demands(project)]


def collected_ribbons(user_id):
    """The submissions of this person that give them a Blue Ribbon: approved with the ribbon (any project, any ship) and handed over by
    Grandma. One that is still waiting at her does not count. The one definition of holding a ribbon."""
    return Submission.objects.filter(project__user_id=user_id, status=rules.APPROVED, ribbon=True, claimed_at__isnull=False)


def holds_ribbon(submission):
    """Whether the person who made this submission already held a Blue Ribbon before it: an EARLIER collected ribbon of theirs."""
    return collected_ribbons(submission.project.user_id).filter(pk__lt=submission.pk).exists()


def holds_ribbon_user(user):
    """Whether this person holds a Blue Ribbon now (staff only if they hold one themselves). A signed out visitor never does."""
    return user.is_authenticated and collected_ribbons(user.pk).exists()


def cookies_for(submission):
    """What this submission's saved review is worth in cookies (rules.award over the demands the project kept, with the permanent
    ribbon term when the person already holds a ribbon, counted once if this review has the ribbon too)."""
    return rules.award(submission.status, tiers_of(submission.project), submission.approved_hours, submission.quality, submission.ribbon,
                       holds_ribbon(submission))


@transaction.atomic
def review(submission, *, by, max_rounds, now=None):
    """Save the reviewer's decision, which is already on `submission` (the admin form put it there). Stamps who and when and works
    out the cookies, then saves only the review fields. Put back to `submitted`, the stamps are cleared. AlreadyCollected once
    the person has been handed the result: the check is made under a lock on the row, so a form opened before the handover cannot
    change it. ValidationError (a sentence for the reviewer, rules.review_problem) for changes requested without a note, or newly asked
    for on the last round (`max_rounds` is the MAX_ROUNDS setting; a row that already has changes requested is not asked again);
    nothing is saved then. When changes are newly asked for, the Slack notice is registered to go out only once the transaction has
    committed (notices.tell_changes_requested: switched off by default, and it never raises). ValidationError (OWN_PROJECT) when `by` is the
    person who made the project, whoever they are: nobody reviews their own work, and nothing is saved."""
    current = Submission.objects.select_for_update().select_related("project__user").get(pk=submission.pk)
    if current.claimed_at is not None:
        raise AlreadyCollected
    if current.project.user_id == by.pk:
        raise ValidationError(OWN_PROJECT)
    changed = any(getattr(current, f) != getattr(submission, f) for f in ("status", "approved_hours", "quality", "ribbon", "public_note", "internal_note"))
    if not changed and current.reviewed_at is not None:
        return submission
    problem = rules.review_problem(submission.status, submission.public_note, current.round, max_rounds, was=current.status)
    if problem:
        raise ValidationError(problem)
    if submission.status == rules.SUBMITTED:
        submission.reviewed_by, submission.reviewed_at, submission.cookies_awarded = None, None, None
    else:
        submission.reviewed_by, submission.reviewed_at, submission.cookies_awarded = by, now or timezone.now(), cookies_for(submission)
    submission.save(update_fields=REVIEW_FIELDS)
    audit.record(
        "submission.review",
        actor=by,
        subject=current.project.user,
        target=submission,
        details={
            "status": submission.status,
            "quality": bool(submission.quality),
            "ribbon": bool(submission.ribbon),
            "approved_hours": str(submission.approved_hours) if submission.approved_hours is not None else None,
            "cookies_awarded": submission.cookies_awarded or 0,
        },
    )
    if rules.newly_asked_for_changes(current.status, submission.status):
        transaction.on_commit(partial(notices.tell_changes_requested, submission.pk))
    return submission


@transaction.atomic
def claim(user, submission_id, *, now=None):
    """Grandma hands over the result of a review, once. Approved: the cookies go on the ledger under the key `submission:{id}`
    (nothing is written for 0 cookies, and a round with changes requested is worth 0) and `claimed_at` is set in the same transaction,
    so a double click or a reload credits once. The project becomes approved, rejected or changes requested (after_claim). Only the
    person's own submission, only a reviewed one. Returns the submission, None if there is nothing of theirs to collect."""
    project_services.lock_person(user)
    submission = Submission.objects.select_for_update().filter(pk=submission_id, project__user=user, status__in=rules.REVIEWED).first()
    if submission is None:
        return None
    if submission.claimed_at:
        return submission
    project = Project.objects.select_for_update().get(pk=submission.project_id)
    if submission.cookies_awarded:
        ledger.credit(user, submission.cookies_awarded, key=f"submission:{submission.pk}",
                      reason=f"Grandma paid for {project.name}")
    submission.claimed_at = now or timezone.now()
    submission.save(update_fields=["claimed_at"])
    if project.status in (project_rules.IN_REVIEW, project_rules.SHIPPED):
        project.status = after_claim(submission)
        project.save(update_fields=["status"])
    audit.record(
        "submission.claim",
        actor=user,
        subject=user,
        target=submission,
        details={
            "cookies": submission.cookies_awarded or 0,
            "project_status": project.status,
        },
    )
    return submission


AFTER_CLAIM = {rules.APPROVED: project_rules.APPROVED, rules.CHANGES_REQUESTED: project_rules.CHANGES_REQUESTED, rules.REJECTED: project_rules.REJECTED}


def after_claim(submission):
    """The project's status once the person has heard the result."""
    return AFTER_CLAIM[submission.status]
