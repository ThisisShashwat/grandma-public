"""What a page may know about a demand: a frozen record of plain fields, never a model (the same boundary as shop/catalog.py).

Each note carries the mood face Grandma would show if this were the one demand taken for a 12 hour project, picked by
program.payout.face: a static picture, never a number, and no payout figure anywhere on it (cookies only on the site).
"""
from dataclasses import dataclass

from program import payout
from program.content.demands import LEVELS, TIERS
from program.content.faces import FACES

DEFAULT_HOURS = 12      # the calculator's starting hours (templates/components/calculator.html); the face is the one it would show


@dataclass(frozen=True)
class Note:
    id: int
    name: str
    line: str           # what Grandma says
    rule: str           # the proper plain-language rule
    tier: int
    tier_label: str     # "Just a thought, dear", "I'm just saying" or "Back in my day"
    level: str          # mild, medium or spicy
    face_file: str      # in static/assets
    face_alt: str
    face_say: str       # her line for that mood


def note(demand):
    face = FACES[payout.face(tiers=(demand.tier,), hours=DEFAULT_HOURS)]
    return Note(id=demand.id, name=demand.name, line=demand.grandma_line, rule=demand.rule, tier=demand.tier,
                tier_label=TIERS[demand.tier], level=LEVELS[demand.tier], face_file=face["file"], face_alt=face["alt"], face_say=face["say"])


def notes(demands):
    return [note(demand) for demand in demands]
