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
    excluded: frozenset = frozenset()      # ids of the subcategories it can NOT be dealt for (none: it fits every subcategory of its categories)


def fits(card, category, subcategory=None):
    """Can this card be dealt for this category and subcategory? THE rule of what a project may hold (docs/projects.md "Switching the
    category or the subcategory"): the category is one of the card's and the subcategory is not one it excludes. No category means any;
    no subcategory is excluded by nothing. projects/services.py `eligible_demands` is the same rule as a query, and a test pins the two."""
    return category is None or (category in card.categories and subcategory not in card.excluded)


def clashes(card, hand):
    """Does the card clash with one already in the hand? The blocklist is symmetric, but both directions are checked."""
    return any(card.id in held.conflicts or held.id in card.conflicts for held in hand)


def candidates(cards, hand, category, subcategory=None):
    """What may still go into the hand, in a fixed order (so a seeded generator always deals the same notes)."""
    held = {card.id for card in hand}
    return sorted((c for c in cards if fits(c, category, subcategory) and c.id not in held and not clashes(c, hand)), key=lambda c: c.id)


def pick(options, rng):
    """One card of `options`: roll a tier among the tiers that still have a card, then a card of that tier."""
    tiers = sorted({card.tier for card in options})
    tier = rng.choices(tiers, weights=[TIER_WEIGHTS[t] for t in tiers])[0]
    return rng.choice([card for card in options if card.tier == tier])


def deal(cards, size, rng, category=None, subcategory=None):
    """The ids of up to `size` cards for `category` and `subcategory`, in the order dealt. A smaller pool (or one that runs out because
    of clashes) simply gives a smaller hand."""
    hand = []
    while len(hand) < size:
        options = candidates(cards, hand, category, subcategory)
        if not options:
            break
        hand.append(pick(options, rng))
    return [card.id for card in hand]


def varies(pool, size):
    """Could two deals from this pool hold different notes? Yes when more notes fit than a hand holds, or when two of them clash (a
    hand must then leave one of the two out). A small pool without clashes is dealt whole every time."""
    return len(pool) > size or any(clashes(card, [other for other in pool if other.id != card.id]) for card in pool)


def can_change(cards, hand, size, category=None, subcategory=None):
    """Could another deal show a different hand from `hand`, the ids the person now holds? No when every deal for this category
    and subcategory holds the same notes and they already hold them all (category Other has three notes for a hand of six), or when
    nothing fits."""
    pool = [card for card in cards if fits(card, category, subcategory)]
    return bool(pool) and (varies(pool, size) or set(hand) != {card.id for card in pool})


def keeps_fit(kept, hand):
    """Is this a legal choice? One to three distinct notes, every one of them in the hand that was dealt."""
    kept = set(kept)
    return MIN_KEEP <= len(kept) <= MAX_KEEP and kept <= set(hand)
