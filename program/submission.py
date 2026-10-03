"""The two admin settings behind the submit page, read as plain data: the boxes a person ticks (SUBMISSION_CHECKS, JSON, each box for
all projects, for software only or for hardware only) and the hosts a playable link may not be on (BLOCKED_HOSTS, one per line).
Pure Python, no Django import: pages/fields.py uses the `parse_*` functions to refuse a bad value in the admin, the submit page uses `checks` and `hosts`, which never fail. A value that
bypassed the admin and is broken falls back to the defaults, because an empty checklist would make "tick every box" meaningless."""
import json
import re
from typing import NamedTuple

from program.content.submission import BLOCKED_HOSTS, CHECKS

MAX_CHECKS = 40
KINDS = ("software", "hardware")
APPLIES_TO = ("all", *KINDS)
KEY = re.compile(r"[a-z][a-z0-9_]{1,39}")
HOST = re.compile(r"(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,24}")


class Check(NamedTuple):
    key: str      # stored with a submission when the box was ticked
    text: str     # what the person reads
    applies_to: str = "all"     # "all", "software" or "hardware": which projects see the box


def default_checks_json():
    return json.dumps(CHECKS, indent=2)


def default_hosts_text():
    return "\n".join(BLOCKED_HOSTS)


def parse_checks(text):
    """The checklist in a JSON text: a list of {"key", "text"} and, optionally, "applies_to" ("all" when missing). ValueError with a
    sentence for anything else."""
    try:
        rows = json.loads(text)
    except (TypeError, ValueError):
        raise ValueError("That is not valid JSON.") from None
    if not isinstance(rows, list) or not 1 <= len(rows) <= MAX_CHECKS:
        raise ValueError(f"Give a list of 1 to {MAX_CHECKS} checks.")
    out = []
    for row in rows:
        if not isinstance(row, dict) or not {"key", "text"} <= set(row) <= {"key", "text", "applies_to"} or not all(isinstance(v, str) for v in row.values()):
            raise ValueError('Each check is {"key": "...", "text": "...", "applies_to": "all"} and nothing else (applies_to is optional).')
        key, words, applies = row["key"], row["text"].strip(), row.get("applies_to", "all")
        if not KEY.fullmatch(key) or any(key == c.key for c in out):
            raise ValueError(f"The key {key!r} must be unique, lowercase letters, digits and underscores, starting with a letter (2 to 40 characters).")
        if not 1 <= len(words) <= 200:
            raise ValueError(f"The text of {key!r} must be 1 to 200 characters.")
        if applies not in APPLIES_TO:
            raise ValueError(f"The applies_to of {key!r} must be one of: {', '.join(APPLIES_TO)}.")
        out.append(Check(key, words, applies))
    return tuple(out)


def _words(text):
    """(the word as typed, the host in it) for each word of a blocked hosts text."""
    for word in re.split(r"[\s,]+", (text or "").strip().lower()):
        if word:
            yield word, word.removeprefix("*").strip(".")


def parse_hosts(text):
    """Blocked hosts from a text, one per line (spaces and commas work too), lowercase, `*.` and leading dots dropped. ValueError for
    a word that is not a host name."""
    out = []
    for word, host in _words(text):
        if not HOST.fullmatch(host):
            raise ValueError(f"{word!r} is not a host name such as streamlit.app.")
        if host not in out:
            out.append(host)
    return tuple(out)


def checks(text):
    """The checklist for the setting's text. A broken text gives the defaults, never an empty or partial list."""
    try:
        return parse_checks(text)
    except ValueError:
        return parse_checks(default_checks_json())


def checks_for(text, kind):
    """The boxes a project of this kind ("software" or "hardware") must tick: the ones for everybody and the ones for its kind. Never
    none (a checklist that shows nothing would make "tick every box" meaningless): if the setting has no box for this kind, the defaults'."""
    def of_kind(rows):
        return tuple(check for check in rows if check.applies_to in ("all", kind))
    return of_kind(checks(text)) or of_kind(checks(default_checks_json()))


def hosts(text):
    """The blocked hosts for the setting's text; words that are not host names are skipped."""
    return tuple(dict.fromkeys(host for _, host in _words(text) if HOST.fullmatch(host)))
