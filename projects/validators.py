"""What a project's name and idea may hold. Both are shown to other people later (every project is public), so invisible,
bidirectional and look-alike characters are refused (they are how names get spoofed); markup is harmless because every
template escapes. Each raises ValidationError, so one rule guards the model, the admin and the dialogue."""
import unicodedata

from django.core.exceptions import ValidationError


def plain_text(value):
    """Only characters you can see: no control, format (zero width, bidi), private use or unassigned characters, and no
    space but the ordinary one (a no-break or ideographic space looks like one and is not)."""
    return all(unicodedata.category(c)[0] != "C" and (c == " " or not unicodedata.category(c).startswith("Z")) for c in value)


def validate_project_name(value):
    if value != value.strip() or not 2 <= len(value) <= 40 or not plain_text(value) or not any(c.isalnum() for c in value):
        raise ValidationError("Two to forty characters, dear, plain ones, and not starting or ending with a space.")


def validate_idea(value):
    if value != value.strip() or not 5 <= len(value) <= 200 or not plain_text(value) or not any(c.isalnum() for c in value):
        raise ValidationError("A sentence will do, dear: five to two hundred plain characters.")


def validate_complaint_line(value):
    """A complaint's title or example: visible characters only, a letter or digit in it, and nothing but the ordinary space."""
    if not plain_text(value) or not any(c.isalnum() for c in value):
        raise ValidationError("Plain words, dear: nothing invisible.")


def validate_complaint_text(value):
    """What a complaint says: the same, with line breaks allowed."""
    validate_complaint_line(value.replace("\n", " "))
