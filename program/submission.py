"""The two admin settings behind the submit page, read as plain data: the boxes a person ticks (SUBMISSION_CHECKS, JSON)
and the hosts a playable link may not be on (BLOCKED_HOSTS, one per line).
Pure Python, no Django import: pages/fields.py uses the `parse_*` functions to refuse a bad value in the admin, the submit page uses `checks` and `hosts`, which never fail. A value that
bypassed the admin and is broken falls back to the defaults, because an empty checklist would make "tick every box" meaningless."""
import json
import re
from typing import NamedTuple

from program.content.submission import BLOCKED_HOSTS, CHECKS

MAX_CHECKS = 40
KEY = re.compile(r"[a-z][a-z0-9_]{1,39}")
HOST = re.compile(r"(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,24}")
HARDWARE_KEYS = frozenset({"demo_works", "bom_exact", "schematic", "editable_cad", "build_new_hours"})


class Check(NamedTuple):
    key: str      # stored with a submission when the box was ticked
    text: str     # what the person reads


def default_checks_json():
    return json.dumps(CHECKS, indent=2)


def default_hosts_text():
    return "\n".join(BLOCKED_HOSTS)


def parse_checks(text):
    """The checklist in a JSON text: a list of {"key", "text"}. Ignores applies_to for backwards compatibility with
    older saved formats, and drops any of the five removed hardware checks. ValueError with a sentence for anything else."""
    try:
        rows = json.loads(text)
    except (TypeError, ValueError):
        raise ValueError("That is not valid JSON.") from None
    if not isinstance(rows, list) or not 1 <= len(rows) <= MAX_CHECKS:
        raise ValueError(f"Give a list of 1 to {MAX_CHECKS} checks.")
    out = []
    for row in rows:
        if not isinstance(row, dict) or not {"key", "text"} <= set(row) <= {"key", "text", "applies_to"}:
            raise ValueError('Each check is {"key": "...", "text": "..."} and nothing else.')
        if not isinstance(row["key"], str) or not isinstance(row["text"], str):
            raise ValueError('Each check is {"key": "...", "text": "..."} and nothing else.')
        key, words = row["key"], row["text"].strip()
        if key in HARDWARE_KEYS:
            continue
        if not KEY.fullmatch(key) or any(key == c.key for c in out):
            raise ValueError(f"The key {key!r} must be unique, lowercase letters, digits and underscores, starting with a letter (2 to 40 characters).")
        if not 1 <= len(words) <= 200:
            raise ValueError(f"The text of {key!r} must be 1 to 200 characters.")
        out.append(Check(key, words))
    if not out:
        raise ValueError(f"Give a list of 1 to {MAX_CHECKS} checks.")
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


def hosts(text):
    """The blocked hosts for the setting's text; words that are not host names are skipped."""
    return tuple(dict.fromkeys(host for _, host in _words(text) if HOST.fullmatch(host)))
