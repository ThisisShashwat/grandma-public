"""Grandma's space on the dashboard: which face she wears and what she says, chosen by where the person's project stands. Pure Python,
no Django, no numbers: moods only, never hours, dollars or rates. A project has no deadline, so she never nags about time."""
from projects import rules


def says(status):
    """(face, line) for a person whose latest project has this status (None: they have never made one)."""
    if status is None:
        return "wave", "Well, dear? Come and tell me what you're going to make."
    if status == rules.DEALING:
        return "note", "I've still got notes out for you. Come and finish picking."
    if status == rules.BUILDING:
        return "clipboard", "Building? Good. I'm watching. I always am."
    if status == rules.IN_REVIEW:
        return "magnifier", "I'm reading what you handed in. Don't hover."
    if status == rules.CHANGES_REQUESTED:
        return "finger", "Nearly, dear. Fix what I asked for and bring it back to me."
    if status == rules.APPROVED:
        return "approved", "Well done, dear. Shall we have another go? My jar is full of demands."
    if status == rules.REJECTED:
        return "nose-up", "Hmph. We'll say no more about it. Try another, and do better."
    return "sideeye", "You left it, dear. I'm not cross. I'm disappointed. It's worse."
