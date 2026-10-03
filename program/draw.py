"""Grandma's draw: which notes she deals. Pure Python, no Django, so tests can replay a deal with a seeded generator.

Tier first: roll how grumpy the next note is (about 1/2 mild, 1/3 medium, 1/6 spicy), then pick a note of that tier, so
beginners are not handed a spicy one by luck. A note the hand already holds, or that clashes with one it holds (the blocklist in
docs/program.md), is never picked. Notes are plain records (`Card`); the caller says which random generator to use:
random.SystemRandom() in production (the draw is a money-adjacent decision, nobody may predict it), a seeded random.Random in tests.
"""
from typing import NamedTuple

TIER_WEIGHTS = {1: 3, 2: 2, 3: 1}      # 3:2:1 is 1/2, 1/3, 1/6 of the rolls
MIN_KEEP, MAX_KEEP = 1, 3              # a fixed rule of the program, not a setting: a project builds around one to three demands


class Card(NamedTuple):
    id: int
    tier: int
    categories: frozenset      # ids of the categories it can be dealt for
    conflicts: frozenset       # ids of the cards it may never share a hand with


def fits(card, category):
    """Can this card be dealt for this category? No category means any."""
    return category is None or category in card.categories


def clashes(card, hand):
    """Does the card clash with one already in the hand? The blocklist is symmetric, but both directions are checked."""
    return any(card.id in held.conflicts or held.id in card.conflicts for held in hand)


def candidates(cards, hand, category):
    """What may still go into the hand, in a fixed order (so a seeded generator always deals the same notes)."""
    held = {card.id for card in hand}
    return sorted((c for c in cards if fits(c, category) and c.id not in held and not clashes(c, hand)), key=lambda c: c.id)


def pick(options, rng):
    """One card of `options`: roll a tier among the tiers that still have a card, then a card of that tier."""
    tiers = sorted({card.tier for card in options})
    tier = rng.choices(tiers, weights=[TIER_WEIGHTS[t] for t in tiers])[0]
    return rng.choice([card for card in options if card.tier == tier])


def deal(cards, size, rng, category=None):
    """The ids of up to `size` cards for `category`, in the order dealt. A smaller pool (or one that runs out because of
    clashes) simply gives a smaller hand."""
    hand = []
    while len(hand) < size:
        options = candidates(cards, hand, category)
        if not options:
            break
        hand.append(pick(options, rng))
    return [card.id for card in hand]


def keeps_fit(kept, hand):
    """Is this a legal choice? One to three distinct notes, every one of them in the hand that was dealt."""
    kept = set(kept)
    return MIN_KEEP <= len(kept) <= MAX_KEEP and kept <= set(hand)
