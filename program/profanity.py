"""Is a name or a suggestion rude? One question, answered by the better-profanity library (its own word list, offline, leetspeak such as sh1t or a$$
included). It matches whole words, so a rude word hidden inside a harmless one (Scunthorpe, class) passes. Where it is used: accounts/validators.py
(display names, project names) and projects/suggestions.py (the suggestion board). A smarter check (an LLM) is meant to be plugged in HERE later: this one
function is the only place that decides."""
from better_profanity import profanity


def is_rude(text):
    return profanity.contains_profanity(text)
