from django import forms
from django.contrib.auth.forms import AuthenticationForm

from accounts.validators import canonical_timezone, polite_unless, validate_display_name, validate_timezone

ASK = {"required": "Fill that in, dear.", "max_length": "Too long, dear."}


class SettingsForm(forms.Form):
    """The three answers a person may change after /welcome/ (templates/pages/settings.html). It only validates, with the rules onboarding uses
    (accounts/validators.py); accounts/profile_edit.py checks the model's again. `regions` is the (code, label) rows of the live REGIONS setting."""

    display_name = forms.CharField(max_length=30, validators=[validate_display_name], error_messages=ASK)
    timezone = forms.CharField(max_length=64, validators=[validate_timezone], error_messages=ASK)
    region = forms.ChoiceField(error_messages={"required": "Pick one, dear.", "invalid_choice": "That is not one of the choices, dear."})

    def __init__(self, *args, regions, own_names=frozenset(), **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["region"].choices = regions
        self.own_names = own_names

    def clean_display_name(self):
        name = self.cleaned_data["display_name"]
        if "display_name" in self.changed_data:       # a name staff typed in the admin is not judged again until the person changes it
            polite_unless(self.own_names)(name)
        return name

    def clean_timezone(self):
        return canonical_timezone(self.cleaned_data["timezone"])


class LoginForm(AuthenticationForm):
    """Django's login form (one wrong-username-or-password message, so nobody can tell which half was wrong) with the
    attributes a password manager and a phone keyboard want, and the site's hand-drawn text box."""

    error_messages = {**AuthenticationForm.error_messages, "invalid_login": "That's not right, dear. Check your username and password: capitals matter."}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["username"].widget.attrs.update(
            {"class": "input", "autocomplete": "username", "autocapitalize": "off", "spellcheck": "false", "autofocus": True})
        self.fields["password"].widget.attrs.update({"class": "input", "autocomplete": "current-password"})
