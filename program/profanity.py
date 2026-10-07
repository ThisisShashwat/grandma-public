"""Is a name or a suggestion rude? One question, answered by the better-profanity library (its own word list, offline, leetspeak such as sh1t or a$$
included). It matches whole words, so a rude word hidden inside a harmless one (Scunthorpe, class) passes.

Two strictnesses, because people's names can be wonky (the owner, 2026-10-07: no false positives): `is_rude_name` is for display names and project names
and lets through the words that are also real names; `is_rude` is for what people write (the suggestion board) and has no exceptions. Where they are
used: accounts/validators.py and projects/suggestions.py. A smarter check (an LLM) is meant to be plugged in HERE later: these two functions are the only
places that decide."""
from better_profanity import Profanity, profanity

#: Words the library lists that are also real names: Wang and Dong are among the commonest surnames and given names in the world, the rest are real first
#: names and surnames. Only `is_rude_name` lets them through.
REAL_NAMES = ("wang", "dong", "dick", "fanny", "willy", "gaylord", "kock")

names = Profanity()
names.load_censor_words(whitelist_words=list(REAL_NAMES))


def is_rude(text):
    return profanity.contains_profanity(text)


def is_rude_name(text):
    return names.contains_profanity(text)
