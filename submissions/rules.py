"""The rules of handing a project in, as plain functions: statuses, which ship comes next, and what a review is worth in cookies.
No Django import and no database, so the maths is decided here and submissions/services.py only applies it. Why each rule exists:
docs/submissions.md."""
from decimal import Decimal
from typing import NamedTuple

from program import payout
from program.content.faces import FACES

SUBMITTED, APPROVED, REJECTED = "submitted", "approved", "rejected"
STATUSES = ((SUBMITTED, "Handed in"), (APPROVED, "Approved"), (REJECTED, "Rejected"))
LABELS = dict(STATUSES)
REVIEWED = (APPROVED, REJECTED)        # a reviewer has decided; the person has not necessarily heard yet

#: The most hours a reviewer can approve in one go. A typo guard (a stray extra zero is hundreds of cookies), not a payout rule:
#: the calculator's slider ends at 60. Raise it here if a real project ever needs more.
MAX_HOURS = Decimal(100)


class Ship(NamedTuple):
    problem: str = ""     # why there can be no next submission, or "" when there can


def next_ship(shipped):
    """What a project may hand in next. A project has exactly one ship."""
    return Ship("You have already handed this one in." if shipped else "")


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
