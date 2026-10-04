"""The plain rule of each demand and the project categories it fits (docs/program.md has the same table).

Kept apart from demands.py on purpose: the home page reads POOL, and this is only for the guides.
Keyed by the demand's name; tests/test_guides_widgets.py checks the keys match POOL exactly.
"""
from typing import NamedTuple

WEB, SOFTWARE, GAMEDEV = "Web", "Software", "Gamedev"
CATEGORIES = (WEB, SOFTWARE, GAMEDEV)


class Rule(NamedTuple):
    plain: str     # what it means, without Grandma's voice
    fits: tuple    # the categories it can be dealt for


#: the blocklist: pairs that are never dealt in one hand (docs/program.md). The projects app seeds it into the database.
CONFLICTS = (
    ("Audio Only", "Big Print"), ("Audio Only", "Two Colors"),
    ("No JavaScript", "URL State"), ("No JavaScript", "Undo Everything"),
)

RULES = {
    "Tiny": Rule("A hard size cap for your category: about 500 lines of code, 10 components, or a 5 cm cube.", CATEGORIES),
    "One Button": Rule("One input controls everything: one key, one tap zone or one physical switch.", (WEB, SOFTWARE, GAMEDEV)),
    "Two Colors": Rule("Only two colors in the whole visual output.", CATEGORIES),
    "Offline": Rule("Works with the network unplugged: no APIs, no CDNs.", (WEB, SOFTWARE, GAMEDEV)),
    "Big Print": Rule("All text and indicators are huge and high contrast.", (WEB, SOFTWARE, GAMEDEV)),
    "No Jargon": Rule("The README is readable by a non-programmer.", CATEGORIES),
    "Audio Only": Rule("Fully usable with the screen off.", (WEB, SOFTWARE, GAMEDEV)),
    "Homemade": Rule("No third-party libraries or engines.", (WEB, SOFTWARE, GAMEDEV)),
    "Single File": Rule("One source file, no build step.", (WEB, SOFTWARE, GAMEDEV)),
    "Plain Text": Rule("All saved data is human-readable text.", (WEB, SOFTWARE, GAMEDEV)),
    "Undo Everything": Rule("Every action can be undone, all the way back to the start.", (WEB, SOFTWARE, GAMEDEV)),
    "No Ifs": Rule("No if statements, switches or ternaries.", (WEB, SOFTWARE, GAMEDEV)),
    "Homegrown Brain": Rule("Any AI model is trained from scratch: no pretrained models, no hosted AI APIs.", (SOFTWARE,)),
    "URL State": Rule("No server or database: all state lives in the URL or the browser.", (WEB,)),
    "No JavaScript": Rule("HTML and CSS only.", (WEB,)),
    "No Images": Rule("No image files: CSS, SVG, canvas or text only.", (WEB, GAMEDEV)),
    "One Screen": Rule("One fixed screen: no scrolling, menus or level loads.", (GAMEDEV,)),
    "Sixty Seconds": Rule("A full playthrough takes under a minute.", (GAMEDEV,)),
}
