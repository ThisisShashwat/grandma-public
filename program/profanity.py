"""Is a name rude? One question, answered by the better-profanity library (its own word list, offline, leetspeak such as sh1t or a$$
included). It matches whole words, so a rude word hidden inside a harmless one (Scunthorpe, class) passes. Where it is used: accounts/validators.py."""
from better_profanity import profanity


def is_rude(text):
    return profanity.contains_profanity(text)
