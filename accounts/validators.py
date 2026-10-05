"""What a Profile field may hold. Each one raises ValidationError, so the same rule guards the model, the admin and the
onboarding dialogue."""
import re
from functools import cache
from zoneinfo import available_timezones

from django.core.exceptions import ValidationError

from program.profanity import is_rude

NAME_CHARS = re.compile(r"[\w .'\-]+")
SLACK_ID = re.compile(r"[UW][A-Z0-9]{8,11}")


def validate_display_name(value):
    """2 to 30 characters: letters, numbers, spaces and . ' - _ . No emoji, symbols, markup or invisible characters:
    this name is shown to other people."""
    if value != value.strip() or not 2 <= len(value) <= 30 or not NAME_CHARS.fullmatch(value) or not any(c.isalnum() for c in value):
        raise ValidationError("Two to thirty characters, dear: letters, numbers, spaces and . ' - only.")


def validate_polite_name(value):
    """A name other people will read (a display name, a project name) must not be rude. Only the dialogue steps use it: it is not on
    the models, so staff can still type any name in the admin."""
    if is_rude(value):
        raise ValidationError("Not in my kitchen, dear. Pick another name.")


def validate_slack_id(value):
    """A Slack member ID (not the username): U or W, then capital letters and digits, 9 to 12 characters in all."""
    if not SLACK_ID.fullmatch(value):
        raise ValidationError("That is not a Slack member ID. It starts with a U or a W, then capital letters and digits, 9 to 12 characters in all.")


@cache
def timezone_names():
    return available_timezones()


def validate_timezone(value):
    """An IANA zone name such as Asia/Kolkata. Checked against the zones that exist, never opened as a path."""
    if value not in timezone_names():
        raise ValidationError("I don't know that time zone. Use a name like Asia/Kolkata or Europe/Berlin.")


def suggested_timezones():
    """The zones offered in the box, without the legacy and technical aliases."""
    return sorted(z for z in timezone_names() if "/" in z and not z.startswith(("Etc/", "posix/", "right/", "SystemV/", "US/")))
