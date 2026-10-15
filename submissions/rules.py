"""The rules of handing a project in, as plain functions: statuses, which round comes next, what a reviewer may decide, and what a
review is worth in cookies. No Django import and no database, so the maths is decided here and submissions/services.py only applies
it. Why each rule exists: docs/submissions.md, docs/changes-requested-plan.md."""
from decimal import Decimal
from typing import NamedTuple

from program import payout
from program.content.faces import FACES

SUBMITTED, APPROVED, CHANGES_REQUESTED, REJECTED = "submitted", "approved", "changes_requested", "rejected"
STATUSES = ((SUBMITTED, "Handed in"), (APPROVED, "Approved"), (CHANGES_REQUESTED, "Changes requested"), (REJECTED, "Rejected"))
LABELS = dict(STATUSES)
REVIEWED = (APPROVED, CHANGES_REQUESTED, REJECTED)        # a reviewer has decided; the person has not necessarily heard yet
#: What the reviewer's form calls them: asking for changes is the normal "no", Rejected is the final one for cheating or spam.
REVIEW_CHOICES = tuple((status, "Ask for changes" if status == CHANGES_REQUESTED else label) for status, label in STATUSES)

#: The most hours a reviewer can approve in one go. A typo guard (a stray extra zero is hundreds of cookies), not a payout rule:
#: the calculator's slider ends at 60. Raise it here if a real project ever needs more.
MAX_HOURS = Decimal(300)

#: The hard ceiling of the MAX_ROUNDS setting (program/runtime.py, which cannot import this) and of Submission.round: a typo guard.
MAX_ROUND_LIMIT = 10

#: What this site did with a message from Ari (AriEvent.outcome, submissions/ari_inbound.py).
APPLIED, NOOP, IGNORED, REFUSED, NEEDS_STAFF, REVERTED = "applied", "noop", "ignored", "refused", "needs_staff", "reverted"
#: Ari decides without our MAX_ROUNDS cap (owner, 2026-10-06): review_problem is asked as if there were always one more round.
NO_ROUND_CAP = MAX_ROUND_LIMIT + 1

STILL_READING = "That one is still with me, dear. I'm reading it. Wait until I've told you what I think."
ALREADY_FINAL = "You have already handed this one in."


class Ship(NamedTuple):
    number: int = 0       # the round the next hand-in would be, 0 when there can be none
    problem: str = ""     # why there can be no next submission, or "" when there can


def next_round(handed_in):
    """What a project may hand in next. `handed_in` is a (round, status) pair for every round it has handed in so far. Nothing yet: round 1.
    After a round with changes requested: the next round, always: a reviewer already granted it, even if the MAX_ROUNDS setting was
    lowered since (the cap is checked when changes are asked for, review_problem); only the hard ceiling MAX_ROUND_LIMIT stops it.
    A round still with Grandma, or an approved or rejected one, means there is nothing to hand in."""
    if not handed_in:
        return Ship(number=1)
    last_round, last_status = max(handed_in)
    if any(status == SUBMITTED for _, status in handed_in):
        return Ship(problem=STILL_READING)
    if last_status != CHANGES_REQUESTED:
        return Ship(problem=ALREADY_FINAL)
    if last_round >= MAX_ROUND_LIMIT:
        return Ship(problem=f"That was round {last_round} of {MAX_ROUND_LIMIT}, dear, and I give no more than that. It stays as it is.")
    return Ship(number=last_round + 1)


def in_review_problem(waiting, cap):
    """Why a person who has `waiting` hand-ins with the reviewers may not hand in another, or "". `cap` is the MAX_IN_REVIEW setting; 0 means no limit."""
    if cap and waiting >= cap:
        return f"I'm already reading {waiting} of yours, dear, and I take no more than {cap} at a time. Wait until I've told you what I think of one of them."
    return ""


def review_problem(status, public_note, number, max_rounds, was=""):
    """Why a reviewer may not save this decision for round `number`, or "". Asking for changes needs a note to tell the person what to
    change, and is not possible on the last round: there is no next round to fix it in. `was` is the status the row has now: a row that
    already has changes requested is not asked again (the cap may have been lowered since), so its cap is not checked, only the note."""
    if status != CHANGES_REQUESTED:
        return ""
    if not public_note.strip():
        return "Asking for changes needs a public note that says what to change. Grandma reads it to the person."
    if was != CHANGES_REQUESTED and number >= max_rounds:
        return f"This is round {number} of {max_rounds}, the last round: there is no next round to fix it in. Approve it or reject it."
    return ""


def ari_hours_problem(hours):
    """Why an approval from Ari is not applied, or "": hours missing, zero, or above the typo guard. Staff look at those (a 4xx would only make Ari drop it)."""
    if hours is None or hours <= 0 or hours > MAX_HOURS:
        return "The approved hours are missing, zero or above the limit."
    return ""


def newly_asked_for_changes(was, status):
    """Whether saving `status` over `was` is the moment changes get asked for: not a row that already has them, not any other decision."""
    return status == CHANGES_REQUESTED and was != CHANGES_REQUESTED


def award(status, tiers, hours, quality, ribbon, ribbon_holder=False):
    """The cookies a review is worth, a whole number: the payout formula for an approved submission, nothing for anything else.
    `tiers` are the tiers of the demands the person kept; `ribbon_holder` is whether they already held a Blue Ribbon from an earlier
    submission (the permanent bonus: the same ribbon term, counted once with `ribbon`, never twice). Rounded the way the page rounds
    (payout.shown)."""
    if status != APPROVED or not hours:
        return 0
    return payout.shown(payout.cookies(tuple(tiers), float(hours), quality, ribbon, ribbon_holder))


def mood(tiers, hours, quality, ribbon):
    """The name of the Grandma face (program/content/faces.py) the payout scale would show for this review: her mood, never a number."""
    return FACES[payout.face(tuple(tiers), float(hours or 0), quality, ribbon)]["name"]
