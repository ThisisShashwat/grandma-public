"""Django validators over the pure link rules (submissions/links.py), for the model's fields. The check against the blocked playable
hosts is not here: it needs the admin settings, so the form makes it (submissions/forms.py)."""
from django.core.exceptions import ValidationError

from projects.validators import plain_text
from submissions import links


def raise_if(problem):
    if problem:
        raise ValidationError(problem)


def validate_web_url(url):
    raise_if(links.web_url_problem(url))


def validate_repo_url(url):
    raise_if(links.repo_problem(url))


def validate_prose(text):
    """Text a person writes for others to read (a description, an AI declaration): plain visible characters, line breaks allowed.
    No control, zero width, bidirectional or private use characters, and no look-alike spaces (they are how text gets spoofed)."""
    if not plain_text(text.replace("\n", " ")):
        raise ValidationError("Plain characters only, dear. Something invisible has crept in there.")
