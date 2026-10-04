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
MAX_HOURS = Decimal(100)

#: The hard ceiling of the MAX_ROUNDS setting (program/runtime.py, which cannot import this) and of Submission.round: a typo guard.
MAX_ROUND_LIMIT = 10

STILL_READING = "That one is still with me, dear. I'm reading it. Wait until I've told you what I think."
ALREADY_FINAL = "You have already handed this one in."


class Ship(NamedTuple):
    number: int = 0       # the round the next hand-in would be, 0 when there can be none
    problem: str = ""     # why there can be no next submission, or "" when there can


def next_round(handed_in, max_rounds):
    """What a project may hand in next. `handed_in` is a (round, status) pair for every round it has handed in so far. Nothing yet: round 1.
    After a round with changes requested: the next round, while there are rounds left. A round still with Grandma, or an approved or
    rejected one, means there is nothing to hand in."""
    if not handed_in:
        return Ship(number=1)
    last_round, last_status = max(handed_in)
    if any(status == SUBMITTED for _, status in handed_in):
        return Ship(problem=STILL_READING)
    if last_status != CHANGES_REQUESTED:
        return Ship(problem=ALREADY_FINAL)
    if last_round >= max_rounds:
        return Ship(problem=f"That was round {last_round} of {max_rounds}, dear, and I give no more than that. It stays as it is.")
    return Ship(number=last_round + 1)


def review_problem(status, public_note, number, max_rounds):
    """Why a reviewer may not save this decision for round `number`, or "". Asking for changes needs a note to tell the person what to
    change, and is not possible on the last round: there is no next round to fix it in."""
    if status != CHANGES_REQUESTED:
        return ""
    if not public_note.strip():
        return "Asking for changes needs a public note that says what to change. Grandma reads it to the person."
    if number >= max_rounds:
        return f"This is round {number} of {max_rounds}, the last round: there is no next round to fix it in. Approve it or reject it."
    return ""


def award(status, tiers, hours, quality, ribbon, ribbon_holder=False):
    """The cookies a review is worth, a whole number: the payout formula for an approved submission, nothing for anything else.
    `tiers` are the tiers of the demands the person kept; `ribbon_holder` is whether they already held a Blue Ribbon from an earlier
    submission (the permanent bonus, payout.CONFIG["ribbon_holder"], 0.0 until the owner sets it). Rounded the way the page rounds
    (payout.shown)."""
    if status != APPROVED or not hours:
        return 0
    return payout.shown(payout.cookies(tuple(tiers), float(hours), quality, ribbon, ribbon_holder))


def mood(tiers, hours, quality, ribbon):
    """The name of the Grandma face (program/content/faces.py) the payout scale would show for this review: her mood, never a number."""
    return FACES[payout.face(tuple(tiers), float(hours or 0), quality, ribbon)]["name"]
