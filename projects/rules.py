"""The project rules as plain functions: statuses and what the next re-deal costs. No Django import, no database, so the maths is
decided here and projects/services.py only applies it. A project has no time limit (docs/projects.md), so there is no clock here.
Why each rule exists: docs/projects.md."""
from datetime import timedelta
from typing import NamedTuple

#: SHIPPED is a leftover of the removed two-ship flow: nothing sets it any more and no view, service or template handles it. It stays in
#: STATUSES and ACTIVE_STATUSES only because the model's choices list it, so dropping it would need a migration.
DEALING, BUILDING, SHIPPED, IN_REVIEW, CHANGES_REQUESTED, APPROVED, REJECTED, ABANDONED = (
    "dealing", "building", "shipped", "in_review", "changes_requested", "approved", "rejected", "abandoned")
STATUSES = ((DEALING, "Talking to Grandma"), (BUILDING, "Building"), (SHIPPED, "Handed in"), (IN_REVIEW, "In review"),
            (CHANGES_REQUESTED, "Changes requested"), (APPROVED, "Approved"), (REJECTED, "Rejected"), (ABANDONED, "Abandoned"))
LABELS = dict(STATUSES)

#: A person has at most one project in WORKING_STATUSES, and the database says so (the Project model's constraint). Dealing is
#: here because a project exists from the moment Grandma deals the hand, before it is confirmed: without it a second hand
#: could be dealt, and re-dealt for free, by starting over.
WORKING_STATUSES = (DEALING, BUILDING)

#: Projects not yet finished (for admin filters and Project.active). A project with changes requested is not finished, but it is not a
#: working one either: the person may fix it while building another.
ACTIVE_STATUSES = (DEALING, BUILDING, SHIPPED, IN_REVIEW, CHANGES_REQUESTED)


class Offer(NamedTuple):
    number: int        # which re-deal this would be: 1 for the first
    free_left: int     # free re-deals left before this one; 0 means this one costs cookies
    cost: int          # cookies this one costs, 0 while free ones are left


def offer(redeals_used, free, cost):
    """The next re-deal of a project that has used `redeals_used` of them: free while the free ones last, then `cost` cookies."""
    free_left = max(0, free - redeals_used)
    return Offer(number=redeals_used + 1, free_left=free_left, cost=0 if free_left else cost)


# Complaints: a person's suggestion for a new demand, read by staff only (docs/projects.md "Complaints").
NEW, READ, USED, DECLINED = "new", "read", "used", "declined"
COMPLAINT_STATUSES = ((NEW, "New"), (READ, "Read"), (USED, "Used"), (DECLINED, "Declined"))

TITLE_MAX, TEXT_MAX, EXAMPLE_MAX = 60, 500, 200          # characters: the demand's name, what and why, one project it would fit

#: At most this many complaints per person in any rolling COMPLAINT_WINDOW. A code constant, not an admin setting: it is spam control.
COMPLAINT_LIMIT = 5
COMPLAINT_WINDOW = timedelta(hours=24)


def tidy(text):
    """Trimmed, with the CRLF line breaks a browser sends made plain LF ones."""
    return text.replace("\r\n", "\n").replace("\r", "\n").strip()
