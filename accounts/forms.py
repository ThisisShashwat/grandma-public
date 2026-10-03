from django.contrib.auth.forms import AuthenticationForm


class LoginForm(AuthenticationForm):
    """Django's login form (one wrong-username-or-password message, so nobody can tell which half was wrong) with the
    attributes a password manager and a phone keyboard want, and the site's hand-drawn text box."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["username"].widget.attrs.update(
            {"class": "input", "autocomplete": "username", "autocapitalize": "off", "spellcheck": "false", "autofocus": True})
        self.fields["password"].widget.attrs.update({"class": "input", "autocomplete": "current-password"})
