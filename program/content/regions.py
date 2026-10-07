"""The regions a person can say they live in, (code, label). XX is the catch-all. Order is the order shown.

REGIONS is the default of the admin setting of the same name (program/runtime.py, one `CODE: Label` per line); onboarding reads the live text through
`regions()`. The model keeps these as its `choices` and a two character column, so a code is exactly two capital letters or digits."""
import re
from functools import lru_cache
from importlib.resources import files

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


EU_COUNTRIES = frozenset("AT BE BG HR CY CZ DK EE FI FR DE GR HU IE IT LV LT LU MT NL PL PT RO SK SI ES SE".split())
COUNTRY_ALIASES = {"GB": "UK"}       # the zone table says GB, the list says UK


@lru_cache(maxsize=1)
def zone_countries():
    """Time zone name -> two letter country code, from the tz database's own table (the `tzdata` package: zone.tab). Empty when the table is missing,
    which only means no guess is ever made."""
    try:
        text = files("tzdata.zoneinfo").joinpath("zone.tab").read_text(encoding="utf-8")
    except (ModuleNotFoundError, FileNotFoundError, OSError):
        return {}
    rows = (line.split("	") for line in text.splitlines() if line and not line.startswith("#"))
    return {row[2]: row[0] for row in rows if len(row) >= 3}


def guess(zone, rows):
    """The code of the region a time zone (the person's own, from their browser, already answered) points at, or "" for none. `rows` is the (code, label)
    pairs on offer. A country that is itself on offer wins (DE when DE is listed), else GB is UK and an EU country is EU when those are listed. The
    catch-all is never guessed. It is only a hint she says aloud: the person still taps their own answer."""
    country = zone_countries().get(zone, "")
    offered = {code for code, _ in rows} - {CATCH_ALL}
    for code in (country, COUNTRY_ALIASES.get(country, ""), "EU" if country in EU_COUNTRIES else ""):
        if code and code in offered:
            return code
    return ""
