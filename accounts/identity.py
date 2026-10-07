"""The identity data HQ's unified record wants for an approved project (name, birthday, address), kept ENCRYPTED and PRIVATE (todo item 2, 2026-10-07).

Two switches, both in the environment. `PII_KEYS` (at least one Fernet key) lets the identity be kept at all: the name Hack Club already sends with the `profile`
scope is then kept, and a display name typed in onboarding that matches one of those names is never censored (`own_names`). `HCA_IDENTITY` on top of it also asks
Hack Club for the extra scopes. With neither set nothing changes and Hack Club is not asked for anything extra. The extras are on only when BOTH `HCA_IDENTITY` is true and `PII_KEYS` holds at least one Fernet key (environment only, never in the admin or the database, newest first). Why both: `birthdate` and
`address` are scopes Hack Club only gives to apps it has marked official (the owner says this app already is, 2026-10-07; if it were not, every sign-in would be refused); and
without a key there is nowhere safe to put them.

What is kept, as ONE encrypted JSON text on the Profile (`Profile.identity`): {"name": "First Last", "birthdate": "YYYY-MM-DD", "address": {street_address,
locality, region, postal_code, country, formatted}}, only the parts Hack Club sent and that pass the checks below. It is refreshed at every Hack Club sign-in
(a person may move house or fix a typo at Hack Club). It is never on a public page, never in the admin, never in a log, a session or the audit log
(the audit log may name that it changed, never what it holds), and nothing reads it yet: the export to HQ waits for HQ's answer to question 11 in docs/hq-questions.md (who stores what).
"""
import json
from datetime import date

from cryptography.fernet import Fernet, InvalidToken, MultiFernet
from django.conf import settings

ADDRESS_KEYS = ("formatted", "street_address", "locality", "region", "postal_code", "country")
MAX_TEXT = 200


class Unreadable(Exception):
    """The sealed identity cannot be opened (no keys, a wrong key, or damage)."""


def enabled():
    """Is Hack Club asked for birthdate and address too?"""
    return bool(settings.HCA_IDENTITY and settings.PII_KEYS)


def stores():
    """May the identity be kept (the name, and the extras when `enabled`)? Only with an encryption key."""
    return bool(settings.PII_KEYS)


def text(value, limit=MAX_TEXT):
    """A claim made fit to keep: stripped text with nothing unprintable, at most `limit` characters, or "" for anything else."""
    return value.strip() if isinstance(value, str) and value.strip() and value.strip().isprintable() and len(value.strip()) <= limit else ""


def clean(userinfo):
    """The identity claims of a sign-in as a small dict (the name always, the birthday and the address only when `enabled`), or {} when Hack Club sent nothing usable. Never raises, never invents."""
    out = {}
    name = " ".join(filter(None, (text(userinfo.get("given_name"), 60), text(userinfo.get("family_name"), 60)))) or text(userinfo.get("name"), 120)
    if name:
        out["name"] = name
    nickname = text(userinfo.get("nickname"), 60)
    if nickname:
        out["nickname"] = nickname
    if enabled():                      # birthday and address only when the owner switched them on (HCA_IDENTITY)
        try:
            born = date.fromisoformat(userinfo.get("birthdate") or "")
            if 1900 <= born.year <= date.today().year:
                out["birthdate"] = born.isoformat()
        except (TypeError, ValueError):
            pass
        raw = userinfo.get("address")
        address = {"formatted": text(raw, 400)} if isinstance(raw, str) else {key: text(raw.get(key)) for key in ADDRESS_KEYS} if isinstance(raw, dict) else {}
        address = {key: value for key, value in address.items() if value}
        if address:
            out["address"] = address
    return out


def fernet():
    if not settings.PII_KEYS:
        raise Unreadable
    return MultiFernet([Fernet(key) for key in settings.PII_KEYS])


def seal(data):
    """The dict as encrypted text for `Profile.identity` (the first key encrypts). Raises Unreadable without keys."""
    try:
        return fernet().encrypt(json.dumps(data, separators=(",", ":"), sort_keys=True).encode()).decode()
    except Unreadable:
        raise
    except Exception:
        raise Unreadable from None


def unseal(sealed):
    """The dict behind `Profile.identity` (any key in PII_KEYS opens it). {} for an empty field. Raises Unreadable when it cannot be opened."""
    if not sealed:
        return {}
    try:
        return json.loads(fernet().decrypt(sealed.encode()))
    except Unreadable:
        raise
    except (InvalidToken, ValueError):
        raise Unreadable from None


def own_names(sealed):
    """The names Hack Club gave for this person, lower case: the whole name, each word of it, and the nickname. A frozenset, empty for no identity, no key or damage.
    A display name that is one of these is the person's own name and is never checked for rude words."""
    try:
        data = unseal(sealed)
    except Unreadable:
        return frozenset()
    names = {data.get("name", ""), data.get("nickname", ""), *data.get("name", "").split(), *data.get("nickname", "").split()}
    return frozenset(" ".join(name.split()).casefold() for name in names if name)
