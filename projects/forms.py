"""The complaint form (templates/pages/complaints.html). It only validates, and every rule is enforced again by projects/complaints.py; the
page draws the fields by hand. The lengths and the characters come from the model, so there is one rule."""
from django import forms

from projects import rules
from projects.models import Complaint, Suggestion


def answer(limit):
    return {"required": "Fill that in, dear.", "max_length": f"{limit} characters at the very most, dear."}


class ComplaintForm(forms.ModelForm):
    class Meta:
        model = Complaint
        fields = ("title", "text", "example")
        error_messages = {"title": answer(rules.TITLE_MAX), "text": answer(rules.TEXT_MAX), "example": answer(rules.EXAMPLE_MAX)}


class SuggestionForm(forms.ModelForm):
    """One suggestion on the board. The kind is posted beside it and checked by projects/suggestions.py; each kind's form has its own prefix."""

    class Meta:
        model = Suggestion
        fields = ("title", "text", "example")
        error_messages = {"title": answer(rules.TITLE_MAX), "text": answer(rules.TEXT_MAX), "example": answer(rules.EXAMPLE_MAX)}
