"""Admin form fields for the settings in program/runtime.py. They refuse values that would break a page."""
import re
from datetime import datetime

from django import forms
from django.core.exceptions import ValidationError
from django.core.validators import URLValidator

ISO_WITH_ZONE = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(:\d{2})?(Z|[+-]\d{2}:\d{2})")
_web_url = URLValidator(schemes=["http", "https"])


class LaunchField(forms.CharField):
    """An ISO 8601 time with a zone, the form the browser's countdown can read."""

    def clean(self, value):
        value = super().clean(value).strip()
        try:
            if not ISO_WITH_ZONE.fullmatch(value):
                raise ValueError
            datetime.fromisoformat(value)
        except ValueError:
            raise ValidationError("Use a time with a zone, like 2026-10-05T12:00:00Z or 2026-10-05T17:30:00+05:30.") from None
        return value


class LinkField(forms.CharField):
    """Empty (a placeholder link), a web link, or a mailto: link. Never javascript: or data: (the links sit in every header)."""

    def __init__(self, **kwargs):
        super().__init__(required=False, max_length=500, **kwargs)

    def clean(self, value):
        value = super().clean(value).strip()
        if value and not value.startswith("mailto:"):
            _web_url(value)
        return value
