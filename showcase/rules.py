"""What the public pages decide, as plain functions: the address a name makes, what a ship's status is to a stranger, Grandma's
mood for it, and the ranks on the cookie board. No Django import and no database, so the rules are decided here and
showcase/public.py only applies them. Why each rule exists: docs/public-pages.md."""
import re
import unicodedata

from submissions import rules as submission_rules

MAX_SLUG = 40


def slug_of(name, fallback):
    """The address-safe form of a name: ASCII letters, digits and single hyphens only, so nothing a person typed can reach a URL
    as markup, a slash or a host. A name with no ASCII letter at all (or an empty one) gets `fallback`."""
    ascii_name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", ascii_name.lower()).strip("-")[:MAX_SLUG].strip("-") or fallback


IN_REVIEW, CHANGES_REQUESTED, APPROVED, RIBBON, REJECTED = "in_review", "changes_requested", "approved", "ribbon", "rejected"
LABELS = {IN_REVIEW: "In review", CHANGES_REQUESTED: "Changes requested", APPROVED: "Approved", RIBBON: "Blue Ribbon", REJECTED: "Rejected"}


def public_status(status, collected, ribbon):
    """What a stranger may be told about a ship. A result the maker has not heard from Grandma yet is still "in review": nobody
    learns a verdict before the person it is about. A ribbon only counts on an approved ship."""
    if not collected or status == submission_rules.SUBMITTED:
        return IN_REVIEW
    if status == submission_rules.REJECTED:
        return REJECTED
    if status == submission_rules.CHANGES_REQUESTED:
        return CHANGES_REQUESTED
    return RIBBON if ribbon else APPROVED


# Grandma's face (a name in talk/portraits.py) and her line for a project that stands like this. Kind: it is somebody's work, said
# to the whole world, and the maker is 13 to 18.
SAYS = {
    IN_REVIEW: ("magnifier", "I'm still reading this one. Don't hover."),
    CHANGES_REQUESTED: ("finger", "Nearly, dear. I've asked for a few changes."),
    APPROVED: ("approved", "Well done, dear. I checked it twice."),
    RIBBON: ("ribbon", "A Blue Ribbon. I do not hand those out."),
    REJECTED: ("sideeye", "Not this time. Everyone gets one of these."),
}


def ranks(totals):
    """Ranks for totals already sorted biggest first: people with the same total share a rank and the next one skips (1, 2, 2, 4)."""
    out, last, rank = [], None, 0
    for place, total in enumerate(totals, start=1):
        if total != last:
            last, rank = total, place
        out.append(rank)
    return out
