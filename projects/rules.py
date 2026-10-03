"""The project rules as plain functions: statuses, the project's time window and what the next re-deal costs. No Django import,
no database, so the maths is decided here and projects/services.py only applies it. Why each rule exists: docs/projects.md."""
from datetime import timedelta
from math import ceil
from typing import NamedTuple

DEALING, BUILDING, SHIPPED, IN_REVIEW, APPROVED, REJECTED, ABANDONED = (
    "dealing", "building", "shipped", "in_review", "approved", "rejected", "abandoned")
STATUSES = ((DEALING, "Talking to Grandma"), (BUILDING, "Building"), (SHIPPED, "Handed in"), (IN_REVIEW, "In review"),
            (APPROVED, "Approved"), (REJECTED, "Rejected"), (ABANDONED, "Abandoned"))
LABELS = dict(STATUSES)

#: A person has at most one project in these statuses, and the database says so (the Project model's constraint). Dealing is
#: here because a project exists from the moment Grandma deals the hand, before it is confirmed: without it a second hand
#: could be dealt, and re-dealt for free, by starting over.
ACTIVE_STATUSES = (DEALING, BUILDING, SHIPPED, IN_REVIEW)

DAY = timedelta(days=1)


class Window(NamedTuple):
    days_left: int     # whole days to the deadline, 0 once it has passed
    ready_in: int      # whole days until it may be handed in, 0 once it may
    late: bool         # past the deadline (shown, never enforced yet)


def window(started_at, now, min_days, max_days):
    """Where a project is in its 10 to 15 day window (the numbers are admin settings). A part-day counts as a day, so a
    project that has just started has all its days left. If the settings disagree (min above max) the deadline is the later."""
    elapsed = now - started_at
    left = timedelta(days=max(min_days, max_days)) - elapsed
    ready = timedelta(days=min_days) - elapsed
    return Window(days_left=max(0, ceil(left / DAY)), ready_in=max(0, ceil(ready / DAY)), late=left <= timedelta(0))


class Offer(NamedTuple):
    number: int        # which re-deal this would be: 1 for the first
    free_left: int     # free re-deals left before this one; 0 means this one costs cookies
    cost: int          # cookies this one costs, 0 while free ones are left


def offer(redeals_used, free, cost):
    """The next re-deal of a project that has used `redeals_used` of them: free while the free ones last, then `cost` cookies."""
    free_left = max(0, free - redeals_used)
    return Offer(number=redeals_used + 1, free_left=free_left, cost=0 if free_left else cost)
