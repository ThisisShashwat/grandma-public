"""Is a name or a suggestion rude? One question, answered by the better-profanity library (its own word list, offline, leetspeak such as sh1t or a$$
included), plus the disguises people actually try that it misses: stretched letters (fuuuck), letters spaced out (f u c k, f.u.c.k) and a digit or symbol
standing for a vowel (f1ck, fvck, f@ck), and Unicode disguises (full-width letters, zero-width characters, Cyrillic or Greek lookalikes). It matches whole words, so a rude word hidden inside a harmless one (Scunthorpe, class) passes. Where it is used:
accounts/validators.py (display names, project names) and projects/suggestions.py (the suggestion board)."""
import re
import unicodedata
from itertools import islice, product

from better_profanity import profanity

REPEATS = re.compile(r"(.)\1{2,}")                      # three or more of one character in a row
SPACED = re.compile(r"\b(?:\w[\s.\-_*]+){2,}\w\b")      # a run of single characters apart: f u c k, f.u.c.k
STANDS_FOR = {"0": "ou", "1": "iul", "3": "e", "4": "a", "5": "s", "7": "t", "@": "a", "$": "s", "!": "i", "v": "u"}
LOOKALIKES = str.maketrans({"а": "a", "е": "e", "о": "o", "р": "p", "с": "c", "х": "x", "у": "y", "і": "i", "ј": "j", "ѕ": "s", "к": "k", "һ": "h", "ԁ": "d", "ɡ": "g", "ⅼ": "l", "ο": "o", "ι": "i", "ν": "v", "κ": "k", "ρ": "p", "τ": "t", "υ": "u"})   # Cyrillic and Greek letters that look Latin
MAX_VARIANTS = 64                                       # a long string of look-alikes is not tried in every combination


def plain(text):
    """The text as a person sees it: full-width letters made ordinary (NFKC), zero-width and other invisible format characters dropped, lookalike letters
    from other alphabets made Latin."""
    text = unicodedata.normalize("NFKC", text)
    return "".join(c for c in text if unicodedata.category(c) != "Cf").translate(LOOKALIKES)


def stretched(text):
    return REPEATS.sub(r"\1", text)


def joined(text):
    """Runs of single characters written apart become one word: 'f u c k' -> 'fuck'."""
    return SPACED.sub(lambda match: re.sub(r"[\s.\-_*]+", "", match.group(0)), text)


def look_alikes(text):
    """The text with each look-alike character read as one of the letters it may stand for (or itself), a few combinations at most."""
    spots = [(i, STANDS_FOR[c] + c) for i, c in enumerate(text) if c in STANDS_FOR]
    if not spots or len(spots) > 6:
        return
    for choice in product(*(options for _, options in spots)):
        out = list(text)
        for (i, _), letter in zip(spots, choice):
            out[i] = letter
        yield "".join(out)


def variants(text):
    base = plain(text).lower()
    for first in dict.fromkeys((base, stretched(base), joined(base), stretched(joined(base)))):
        yield first
        yield from islice(look_alikes(first), MAX_VARIANTS)


def is_rude(text):
    return any(profanity.contains_profanity(variant) for variant in variants(text))
