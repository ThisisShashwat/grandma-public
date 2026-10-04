"""Grandma's demands: the pool the fridge deals from. Rules and categories live in docs/program.md."""
from typing import NamedTuple


class Demand(NamedTuple):
    name: str
    line: str     # what Grandma says
    tier: int     # 1 mild, 2 medium, 3 spicy


TIERS = {1: "Just a thought, dear", 2: "I'm just saying", 3: "Back in my day"}
LEVELS = {1: "mild", 2: "medium", 3: "spicy"}

POOL = [
    Demand("Tiny", "Everything I own fits in one cookie tin. So should this.", 2),
    Demand("One Button", "I only ever press the +30 seconds button on the microwave.", 2),
    Demand("Two Colors", "I only own two crayons. Use them wisely.", 1),
    Demand("Offline", "The internet is broken again, so it had better work without it.", 1),
    Demand("Big Print", "I can't read that tiny writing, dear. Make it big.", 1),
    Demand("No Jargon", "Explain it to me like I'm your grandmother. I am your grandmother.", 1),
    Demand("Audio Only", "Turn that screen off and tell me what's happening, dear.", 3),
    Demand("Homemade", "I don't trust anything I didn't bake myself.", 2),
    Demand("Single File", "I keep everything in one drawer, and I know exactly where.", 2),
    Demand("Plain Text", "If I can't open it in Notepad, I don't want it.", 1),
    Demand("Undo Everything", "Everybody makes mistakes, dear. Let me take that back.", 2),
    Demand("No Ifs", "In my day we didn't say 'if'. We just did it right.", 3),
    Demand("Homegrown Brain", "I don't trust a brain I didn't raise myself.", 3),
    Demand("URL State", "Everything you need is on the note. Don't lose the note.", 2),
    Demand("No JavaScript", "Back in my day a website was words and a picture, and we liked it.", 3),
    Demand("No Images", "Pictures cost money. Draw it with what you've got.", 2),
    Demand("One Screen", "One room, one game, no wandering off.", 1),
    Demand("Sixty Seconds", "Dinner's in a minute. Make it quick.", 1),
]
