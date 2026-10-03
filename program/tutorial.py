"""How much of the tutorial a person sees. Pure Python, no Django.

The tutorial has two parts: 1 is how Help Grandma Out works, 2 is how cookies and the Pantry work. How much of it plays
depends on how experienced the person says they are (three admin settings, one per level, each holding a depth below).
"""

# depth value, what the admin dropdown calls it
DEPTHS = (
    ("both", "Both parts"),
    ("second", "Part two only (cookies and the Pantry)"),
    ("offer", "One line: offer to skip, play both parts if they say yes"),
    ("none", "Nothing"),
)

BOTH = frozenset({1, 2})


def parts(enabled, depth, took_offer):
    """The set of tutorial parts (1 and 2) to play for this depth. `took_offer` is True once a person said "show me"."""
    if not enabled:
        return frozenset()
    if depth == "both" or (depth == "offer" and took_offer):
        return BOTH
    if depth == "second":
        return frozenset({2})
    return frozenset()


def offers_skip(enabled, depth):
    """True when the one-line skip offer should be asked at all."""
    return enabled and depth == "offer"
