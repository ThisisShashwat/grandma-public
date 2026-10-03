"""The note a person fills in to hand a project to Grandma. The form only validates (every rule is enforced here, on the server, whatever
the page showed); the page draws the fields by hand (templates/pages/submit.html). The checklist and the blocked playable hosts
come from the admin settings (program/runtime.py), so the form is built per request with them."""
import re

from django import forms
from django.core.exceptions import ValidationError

from program import submission
from submissions import images, links
from submissions.validators import validate_prose

NOT_ALL_TICKED = "Every box, dear. If one of them isn't true, you don't hand it in."
ANSWER = {"required": "Fill that in, dear."}


class SubmitForm(forms.Form):
    repo_url = forms.CharField(max_length=links.MAX_LENGTH, error_messages=ANSWER)
    playable_url = forms.CharField(max_length=links.MAX_LENGTH, error_messages=ANSWER)
    description = forms.CharField(min_length=20, max_length=1500, error_messages={**ANSWER, "min_length": "A sentence or two at least, dear. What is it, and what does it do?"})
    screenshot = forms.FileField(error_messages={"required": "I need a screenshot, dear.", "empty": "That file is empty, dear.", "missing": "I need a screenshot, dear."})
    recording_url = forms.CharField(required=False, max_length=links.MAX_LENGTH)
    ai_declaration_text = forms.CharField(required=False, max_length=1000)
    declarations = forms.MultipleChoiceField(required=False)

    def __init__(self, *args, cfg, **kwargs):
        super().__init__(*args, **kwargs)
        self.checks = submission.checks(cfg.SUBMISSION_CHECKS)
        self.blocked_hosts = submission.hosts(cfg.BLOCKED_HOSTS)
        self.max_bytes = cfg.SCREENSHOT_MAX_MB * 1024 * 1024
        self.fields["declarations"].choices = [(check.key, check.text) for check in self.checks]

    def clean_repo_url(self):
        return self.checked(self.cleaned_data["repo_url"], links.repo_problem(self.cleaned_data["repo_url"]))

    def clean_playable_url(self):
        return self.checked(self.cleaned_data["playable_url"], links.playable_problem(self.cleaned_data["playable_url"], self.blocked_hosts))

    def clean_recording_url(self):
        url = self.cleaned_data["recording_url"]
        return self.checked(url, links.web_url_problem(url) if url else "")

    def clean_description(self):
        return prose(self.cleaned_data["description"])

    def clean_ai_declaration_text(self):
        return prose(self.cleaned_data["ai_declaration_text"])

    def clean_declarations(self):
        ticked = set(self.cleaned_data["declarations"])
        if ticked != {check.key for check in self.checks}:
            raise ValidationError(NOT_ALL_TICKED)
        return [check.key for check in self.checks]

    def clean_screenshot(self):
        return images.clean_screenshot(self.cleaned_data["screenshot"], self.max_bytes)

    @staticmethod
    def checked(value, problem):
        if problem:
            raise ValidationError(problem)
        return value


def prose(text):
    """Text for people to read, with its line breaks tidied (a browser sends \\r\\n). validate_prose refuses what cannot be seen."""
    text = re.sub(r"[ \t]*\r?\n[ \t]*", "\n", text.strip())
    validate_prose(text)
    return text
