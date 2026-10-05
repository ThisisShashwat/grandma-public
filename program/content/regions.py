"""The regions a person can say they live in, (code, label). XX is the catch-all. Order is the order shown.

REGIONS is the default of the admin setting of the same name (program/runtime.py, one `CODE: Label` per line); onboarding reads the live text through
`regions()`. The model keeps these as its `choices` and a two character column, so a code is exactly two capital letters or digits."""
import re

CODE = re.compile(r"[A-Z0-9]{2}")
CATCH_ALL = "XX"
MAX_LABEL = 60

REGIONS = [
    ("US", "United States"),
    ("EU", "Europe (EU)"),
    ("UK", "United Kingdom"),
    ("IN", "India"),
    ("CA", "Canada"),
    ("AU", "Australia"),
    ("XX", "Somewhere else"),
]


def default_text():
    return "\n".join(f"{code}: {label}" for code, label in REGIONS)


def parse(text):
    """The regions in a text, one `CODE: Label` per line (blank lines skipped), as (code, label) pairs in the order written. ValueError with a
    sentence for a bad line, a repeated code, fewer than two regions or no XX line."""
    rows = []
    for number, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            continue
        code, colon, label = (part.strip() for part in line.partition(":"))
        if not colon or not CODE.fullmatch(code):
            raise ValueError(f"Line {number}: start with a code of two capital letters or digits, a colon and the label, like IN: India.")
        if not 1 <= len(label) <= MAX_LABEL:
            raise ValueError(f"Line {number}: the label of {code} must be 1 to {MAX_LABEL} characters.")
        if any(code == seen for seen, _ in rows):
            raise ValueError(f"Line {number}: the code {code} is used twice.")
        rows.append((code, label))
    if len(rows) < 2:
        raise ValueError("Give at least two regions.")
    if CATCH_ALL not in (code for code, _ in rows):
        raise ValueError(f"Keep the {CATCH_ALL} line (the catch-all, like XX: Somewhere else): people who live anywhere else pick it.")
    return tuple(rows)


def regions(text):
    """The regions for the setting's text. A broken text gives the defaults, never an empty or partial list."""
    try:
        return parse(text)
    except ValueError:
        return tuple(REGIONS)
