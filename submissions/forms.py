"""The note a person fills in to hand a project to Grandma. The form only validates (every rule is enforced here, on the server, whatever
the page showed); the page draws the fields by hand (templates/pages/submit.html). The checklist and the blocked playable hosts
come from the admin settings (program/runtime.py), so the form is built per request with them. The order of work is cheap to costly: the
fields, then the business check the view hands in as `precheck` (the hours, services.check_hours), and only then the picture is decoded."""
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
    declarations = forms.MultipleChoiceField(required=False, error_messages={"invalid_choice": NOT_ALL_TICKED})

    def __init__(self, *args, cfg, precheck=None, **kwargs):
        """The boxes shown, all of which must be ticked, are the checks from the settings. `precheck()`: the cheap business checks of the
        hand-in (no arguments, raising ValidationError), run before the screenshot is decoded."""
        super().__init__(*args, **kwargs)
        self.precheck = precheck
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
        upload = self.cleaned_data["screenshot"]
        if upload.size > self.max_bytes:
            raise ValidationError(images.too_big_file(self.max_bytes))
        return upload

    def clean(self):
        """The picture is only decoded and re-encoded (the costly part, images.py) once everything else is right (the fields and the
        view's precheck), so a stream of half-filled forms costs next to nothing."""
        cleaned = super().clean()
        if not self.errors:
            run_precheck(self, self.precheck)
        if not self.errors and "screenshot" in cleaned:
            try:
                cleaned["screenshot"] = images.clean_screenshot(cleaned["screenshot"], self.max_bytes)
            except ValidationError as error:
                self.add_error("screenshot", error)
        return cleaned

    @staticmethod
    def checked(value, problem):
        if problem:
            raise ValidationError(problem)
        return value


def run_precheck(form, check, *arguments):
    """A cheap business check the view handed the form (`check`, or None for none): its refusal becomes the form's own problem, so the
    costly work after it (decoding a picture) never starts."""
    if check is None:
        return
    try:
        check(*arguments)
    except ValidationError as error:
        form.add_error(None, error)


def prose(text):
    """Text for people to read, with its line breaks tidied (a browser sends \\r\\n). validate_prose refuses what cannot be seen."""
    text = re.sub(r"[ \t]*\r?\n[ \t]*", "\n", text.strip())
    validate_prose(text)
    return text
