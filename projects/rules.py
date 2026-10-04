"""The project rules as plain functions: statuses and what the next re-deal costs. No Django import, no database, so the maths is
decided here and projects/services.py only applies it. A project has no time limit (docs/projects.md), so there is no clock here.
Why each rule exists: docs/projects.md."""
from typing import NamedTuple

DEALING, BUILDING, SHIPPED, IN_REVIEW, APPROVED, REJECTED, ABANDONED = (
    "dealing", "building", "shipped", "in_review", "approved", "rejected", "abandoned")
STATUSES = ((DEALING, "Talking to Grandma"), (BUILDING, "Building"), (SHIPPED, "Handed in"), (IN_REVIEW, "In review"),
            (APPROVED, "Approved"), (REJECTED, "Rejected"), (ABANDONED, "Abandoned"))
LABELS = dict(STATUSES)

#: A person has at most one project in WORKING_STATUSES, and the database says so (the Project model's constraint). Dealing is
#: here because a project exists from the moment Grandma deals the hand, before it is confirmed: without it a second hand
#: could be dealt, and re-dealt for free, by starting over.
WORKING_STATUSES = (DEALING, BUILDING)

#: Projects not yet finished (for admin filters and Project.active).
ACTIVE_STATUSES = (DEALING, BUILDING, SHIPPED, IN_REVIEW)


class Offer(NamedTuple):
    number: int        # which re-deal this would be: 1 for the first
    free_left: int     # free re-deals left before this one; 0 means this one costs cookies
    cost: int          # cookies this one costs, 0 while free ones are left


def offer(redeals_used, free, cost):
    """The next re-deal of a project that has used `redeals_used` of them: free while the free ones last, then `cost` cookies."""
    free_left = max(0, free - redeals_used)
    return Offer(number=redeals_used + 1, free_left=free_left, cost=0 if free_left else cost)
