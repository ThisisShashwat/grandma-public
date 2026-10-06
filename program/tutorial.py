"""How much of the tutorial a person sees. Pure Python, no Django.

The tutorial has three parts. 1 is how Help Grandma Out works and 2 is how cookies and the Pantry work: they are about THIS program, so they
ALWAYS play (owner, 2026-10-07; only the whole tutorial switch can turn them off). 0 is the Hack Club basics (what shipping means, You Ship We Ship,
what a grant is): that is the part experience can skip, by three admin settings, one per level, each holding a depth below.
"""

# depth value, what the admin dropdown calls it (for the Hack Club basics)
DEPTHS = (
    ("play", "Play the Hack Club basics"),
    ("offer", "One line: offer to skip, play them if they say yes"),
    ("none", "Skip them"),
)

ALWAYS = frozenset({1, 2})


def parts(enabled, depth, took_offer):
    """The set of tutorial parts (0, 1 and 2) to play for this depth. `took_offer` is True once a person said "show me". Parts 1 and 2 always
    play while the tutorial is on; part 0 (the Hack Club basics) plays for "play", and for "offer" once they said yes."""
    if not enabled:
        return frozenset()
    if depth == "play" or (depth == "offer" and took_offer) or depth not in ("offer", "none"):
        return ALWAYS | {0}
    return ALWAYS


def offers_skip(enabled, depth):
    """True when the one-line skip offer should be asked at all."""
    return enabled and depth == "offer"
