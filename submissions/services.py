"""Everything that changes a submission, and the reads the pages need. Rules are in rules.py (pure); this layer applies them to the
database. Every change takes the same locks as projects and the ledger, in the same order: the person's Profile row first, then the
rows being changed, so two clicks on the same button cannot both win (SQLite is in IMMEDIATE mode, settings.py; on Postgres the row
locks do the work). The cookie handover writes the ledger only through ledger.services, under the key `submission:{id}`."""
from functools import partial

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from audit import services as audit
from ledger import rules as ledger_rules
from ledger import services as ledger
from pages.live import live
from projects import rules as project_rules
from projects import services as project_services
from projects.models import Project
from submissions import ari, notices, rules
from submissions.models import Submission

NOTHING_TO_SHIP = "You have nothing to hand in right now, dear. Only a project you are building."
CHECK_YOUR_HOURS = "Check your hours first, dear. I won't take it until Hackatime has shown me some time on this project. Use the Check my hours button on the note."
UNFIT_NOTES = "One of the notes you kept doesn't suit this kind of project, dear. Swap it with Change my demands on your project page. Stuck? Ask the staff in the Slack."
OWN_PROJECT = "You cannot review your own project. Ask another reviewer."
REVIEW_FIELDS = ("status", "approved_hours", "quality", "ribbon", "public_note", "internal_note", "reviewed_by", "reviewed_at", "cookies_awarded")
ARI_FIELDS = REVIEW_FIELDS + ("reviewer_label", "demand_checks", "needs_staff")
CLEARED = {"status": rules.SUBMITTED, "approved_hours": None, "quality": False, "ribbon": False, "public_note": "", "internal_note": "", "reviewed_by": None,
           "reviewed_at": None, "cookies_awarded": None, "claimed_at": None, "reviewer_label": "", "demand_checks": []}      # a decision taken back


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
    if ari.enabled(live()):
        ari.queue_and_try(submission)
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


def review_details(submission):
    """The audit details of a saved decision (who made it is the entry's actor)."""
    return {
        "status": submission.status,
        "quality": bool(submission.quality),
        "ribbon": bool(submission.ribbon),
        "approved_hours": str(submission.approved_hours) if submission.approved_hours is not None else None,
        "cookies_awarded": submission.cookies_awarded or 0,
    }


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
        details=review_details(submission),
    )
    if rules.newly_asked_for_changes(current.status, submission.status):
        transaction.on_commit(partial(notices.tell_changes_requested, submission.pk))
    return submission


def payout_key(user, submission):
    """The ledger key of this submission's payout: `submission:{id}`, and `submission:{id}:v{n}` after Ari took the first payout back n times (each time a debit
    under `submission:{id}:revert:...` was written), so one approval pays once overall and a re-approval after a revert can pay again."""
    reverts = ledger.count_keys(user, f"submission:{submission.pk}:revert:")
    return f"submission:{submission.pk}" + (f":v{reverts}" if reverts else "")


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
        ledger.credit(user, submission.cookies_awarded, key=payout_key(user, submission), reason=f"Grandma paid for {project.name}")
    submission.claimed_at = now or timezone.now()
    submission.save(update_fields=["claimed_at"])
    if project.status == project_rules.IN_REVIEW:
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


# Ari's decisions (docs/submissions.md "Ari"): the actor is the system, so no `reviewer`; the audit details say only via, event and delivery, never an email or a name

def locked_for_ari(submission_id):
    """The submission row, locked, after its person's Profile row (the lock order of everything in this file)."""
    project_services.lock_person(Submission.objects.select_related("project__user").get(pk=submission_id).project.user)
    return Submission.objects.select_for_update().select_related("project__user").get(pk=submission_id)


def ari_details(event, delivery, **more):
    return {"via": "ari", "event": event, "delivery": delivery, **more}


def flag_staff(submission, event, delivery, why):
    """Something from Ari this site must not apply by itself: nothing changes but the flag the admin lists (`why` is one fixed word)."""
    submission.needs_staff = True
    submission.save(update_fields=["needs_staff"])
    audit.record("submission.ari_needs_staff", subject=submission.project.user, target=submission, details=ari_details(event, delivery, why=why))


@transaction.atomic
def apply_ari_decision(submission_id, *, event, delivery, status, approved_hours=None, quality=False, ribbon=False, public_note="", internal_note="", reviewer_label="",
                       demand_checks=(), now=None):
    """Save the decision an Ari reviewer made (already a confirmed one: second pass is on there), as `review` would, without a reviewer user. Returns what happened:
    NOOP (the same decision is already stored), APPLIED, IGNORED (the project is no longer in review: abandoned, or finished by staff), or REFUSED / NEEDS_STAFF with
    `needs_staff` set and nothing else changed: a different decision once the person collected, a different one after staff decided in the admin, an approval with no,
    zero or too many hours, changes without a note. The round cap is not applied (the owner, 2026-10-06). A decision different from the stored one replaces it while it
    is not collected. The cookies are worked out as always and paid only when the person collects (`claim`)."""
    current = locked_for_ari(submission_id)
    new = {"status": status, "approved_hours": approved_hours, "quality": quality, "ribbon": ribbon, "public_note": public_note[:1000], "internal_note": internal_note[:2000],
           "reviewer_label": reviewer_label[:254], "demand_checks": list(demand_checks)}
    if current.reviewed_at is not None and all(getattr(current, field) == value for field, value in new.items()):
        return rules.NOOP
    if current.claimed_at:
        flag_staff(current, event, delivery, "collected")
        return rules.NEEDS_STAFF
    if current.project.status != project_rules.IN_REVIEW:
        return rules.IGNORED
    if current.reviewed_by_id:
        flag_staff(current, event, delivery, "staff decided")
        return rules.NEEDS_STAFF
    problem = rules.review_problem(status, new["public_note"], current.round, rules.NO_ROUND_CAP, was=current.status)
    problem = problem or (rules.ari_hours_problem(approved_hours) if status == rules.APPROVED else "")
    if problem:
        flag_staff(current, event, delivery, "refused")
        return rules.REFUSED
    was = current.status
    for field, value in new.items():
        setattr(current, field, value)
    current.reviewed_by, current.reviewed_at, current.cookies_awarded = None, now or timezone.now(), cookies_for(current)
    current.save(update_fields=ARI_FIELDS)
    audit.record("submission.review", subject=current.project.user, target=current, details=review_details(current) | ari_details(event, delivery))
    if rules.newly_asked_for_changes(was, status):
        transaction.on_commit(partial(notices.tell_changes_requested, current.pk))
    return rules.APPLIED


@transaction.atomic
def revert_ari_decision(submission_id, *, event, delivery, needs_staff):
    """Ari took a decision back (reverted or requeued): block and revert here too. The submission goes back to handed in with the decision cleared. Already collected: the
    cookies are taken back with one debit (`submission:{id}:revert:{delivery}`, so a repeat writes once) and the project goes back to in review, but ONLY while the person's
    balance covers it and this is the project's latest round; otherwise nothing changes except the staff flag (we never go below zero, and a half undone state could pay
    twice). `needs_staff` flags it for staff either way (a reverted ship may never come back to Ari's queue). A decision staff made in the admin is never undone (NOOP), and a
    submission with no decision stored is only flagged when Ari reverted (NEEDS_STAFF the first time). Returns NOOP, REVERTED or NEEDS_STAFF."""
    current = locked_for_ari(submission_id)
    if current.reviewed_by_id:              # staff decided it in the admin: Ari taking back its own decision is not about that one
        return rules.NOOP
    if current.status == rules.SUBMITTED:   # nothing here to undo; but a reverted ship is out of Ari's queue for good, so staff must hear that (once)
        if needs_staff and not current.needs_staff:
            flag_staff(current, event, delivery, "reverted")
            return rules.NEEDS_STAFF
        return rules.NOOP
    user, project, owed = current.project.user, current.project, 0
    if current.claimed_at:
        owed = current.cookies_awarded or 0
        why = "old round" if latest_round(project).pk != current.pk else "spent" if owed > ledger.balance(user) else ""
        if why:
            flag_staff(current, event, delivery, why)
            return rules.NEEDS_STAFF
        if owed:
            ledger.debit(user, owed, reason=f"Grandma took back the cookies for {project.name}", key=f"submission:{current.pk}:revert:{delivery}", kind=ledger_rules.ADJUSTMENT)
        locked = Project.objects.select_for_update().get(pk=project.pk)
        if locked.status in AFTER_CLAIM.values():
            locked.status = project_rules.IN_REVIEW
            locked.save(update_fields=["status"])
    for field, value in CLEARED.items():
        setattr(current, field, value)
    current.needs_staff = current.needs_staff or needs_staff
    current.save(update_fields=ARI_FIELDS + ("claimed_at",))
    audit.record("submission.ari_revert", subject=user, target=current, details=ari_details(event, delivery, cookies_taken=owed))
    return rules.REVERTED


@transaction.atomic
def clear_needs_staff(submission_id, *, by):
    """Staff dealt with what Ari sent: take the flag off. Returns whether it was on."""
    submission = Submission.objects.select_for_update().select_related("project").get(pk=submission_id)
    if not submission.needs_staff:
        return False
    submission.needs_staff = False
    submission.save(update_fields=["needs_staff"])
    audit.record("submission.needs_staff_cleared", actor=by, subject=submission.project.user, target=submission)
    return True


AFTER_CLAIM = {rules.APPROVED: project_rules.APPROVED, rules.CHANGES_REQUESTED: project_rules.CHANGES_REQUESTED, rules.REJECTED: project_rules.REJECTED}


def after_claim(submission):
    """The project's status once the person has heard the result."""
    return AFTER_CLAIM[submission.status]
