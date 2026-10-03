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

DESIGN, BUILD = "design", "build"      # hardware has two ships. A software submission has no stage at all: it has exactly one ship
STAGES = ((DESIGN, "Design ship"), (BUILD, "Build ship"))
STAGE_LABELS = dict(STAGES) | {None: "Ship"}

#: The most hours a reviewer can approve in one go. A typo guard (a stray extra zero is hundreds of cookies), not a payout rule:
#: the calculator's slider ends at 60. Raise it here if a real project ever needs more.
MAX_HOURS = Decimal(100)


class Ship(NamedTuple):
    stage: str | None     # the stage the next submission would be: None for software, "design" or "build" for hardware
    problem: str          # why there can be no next submission, or "" when there can


def next_ship(hardware, shipped):
    """What a project may hand in next. `shipped` is what it has handed in so far, as (stage, status, claimed) rows. Software has
    one ship. Hardware has a design ship, and a build ship only once the design was approved AND the person has heard it from Grandma."""
    if not hardware:
        return Ship(None, "" if not shipped else "You have already handed this one in.")
    done = {stage: (status, claimed) for stage, status, claimed in shipped}
    if DESIGN not in done:
        return Ship(DESIGN, "")
    status, claimed = done[DESIGN]
    if status != APPROVED or not claimed:
        return Ship(None, "Your design is not through yet.")
    return Ship(BUILD, "") if BUILD not in done else Ship(None, "You have already handed in the build.")


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
