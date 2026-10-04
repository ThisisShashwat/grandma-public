"""The plain rule of each demand and the project categories it fits (docs/program.md has the same table).

Kept apart from demands.py on purpose: the home page reads POOL, and this is only for the guides.
Keyed by the demand's name; tests/test_guides_widgets.py checks the keys match POOL exactly.
"""
from typing import NamedTuple

WEB, SOFTWARE, GAMEDEV, OTHER = "Web", "Software", "Gamedev", "Other"
MAIN = (WEB, SOFTWARE, GAMEDEV)
CATEGORIES = (*MAIN, OTHER)     # every category: a rule that uses this fits any project, Other included


class Rule(NamedTuple):
    plain: str     # what it means, without Grandma's voice
    fits: tuple    # the categories it can be dealt for

    @property
    def anything(self):
        """True for the demands that fit any project (and so are dealt for Other); not true for one that fits only the three main ones."""
        return set(self.fits) == set(CATEGORIES)


#: the blocklist: pairs that are never dealt in one hand (docs/program.md). The projects app seeds it into the database.
CONFLICTS = (
    ("Audio Only", "Big Print"), ("Audio Only", "Two Colors"),
    ("No JavaScript", "URL State"), ("No JavaScript", "Undo Everything"),
)

RULES = {
    "Tiny": Rule("A hard size cap for your category: about 500 lines of code or 10 components.", CATEGORIES),
    "One Button": Rule("One input controls everything: one key or one tap zone.", MAIN),
    "Two Colors": Rule("Only two colors in the whole visual output.", CATEGORIES),
    "Offline": Rule("Works with the network unplugged: no APIs, no CDNs.", MAIN),
    "Big Print": Rule("All text and indicators are huge and high contrast.", MAIN),
    "No Jargon": Rule("The README is readable by a non-programmer.", CATEGORIES),
    "Audio Only": Rule("Fully usable with the screen off.", MAIN),
    "Homemade": Rule("No third-party libraries or engines.", MAIN),
    "Single File": Rule("One source file, no build step.", MAIN),
    "Plain Text": Rule("All saved data is human-readable text.", MAIN),
    "Undo Everything": Rule("Every action can be undone, all the way back to the start.", MAIN),
    "No Ifs": Rule("No if statements, switches or ternaries.", MAIN),
    "Homegrown Brain": Rule("Any AI model is trained from scratch: no pretrained models, no hosted AI APIs.", (SOFTWARE,)),
    "URL State": Rule("No server or database: all state lives in the URL or the browser.", (WEB,)),
    "No JavaScript": Rule("HTML and CSS only.", (WEB,)),
    "No Images": Rule("No image files: CSS, SVG, canvas or text only.", (WEB, GAMEDEV)),
    "One Screen": Rule("One fixed screen: no scrolling, menus or level loads.", (GAMEDEV,)),
    "Sixty Seconds": Rule("A full playthrough takes under a minute.", (GAMEDEV,)),
}
