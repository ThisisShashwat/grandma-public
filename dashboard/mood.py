"""Grandma's space on the dashboard: which face she wears and what she says, chosen by where the person's project stands. Pure Python,
no Django, no numbers except days left: cookies and moods only, never hours, dollars or rates."""
from projects import rules

SOON = 3          # days left at or under which she starts to nag


def says(status, days_left=None, late=False):
    """(face, line) for a person whose latest project has this status (None: they have never made one)."""
    if status is None:
        return "wave", "Well, dear? Come and tell me what you're going to make."
    if status == rules.DEALING:
        return "note", "I've still got notes out for you. Come and finish picking."
    if status == rules.BUILDING and late:
        return "shocked", "The deadline's gone by, dear. Hand it in before I change my mind about you."
    if status == rules.BUILDING and days_left is not None and days_left <= SOON:
        return "sideeye", f"{days_left} {'day' if days_left == 1 else 'days'}, dear. Tick tock."
    if status == rules.BUILDING:
        return "clipboard", "Building? Good. I'm watching. I always am."
    if status in (rules.SHIPPED, rules.IN_REVIEW):
        return "magnifier", "I'm reading what you handed in. Don't hover."
    if status == rules.APPROVED:
        return "approved", "Well done, dear. Shall we have another go? My jar is full of demands."
    if status == rules.REJECTED:
        return "nose-up", "Hmph. We'll say no more about it. Try another, and do better."
    return "sideeye", "You left it, dear. I'm not cross. I'm disappointed. It's worse."
