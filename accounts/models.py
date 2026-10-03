from django.conf import settings
from django.db import models
from django.db.models import Q

from accounts.validators import validate_display_name, validate_slack_id, validate_timezone
from program.content.expertise import EXPERTISE
from program.content.regions import REGIONS

FILLED_IN = ("display_name", "slack_id", "region", "timezone", "expertise")


class Profile(models.Model):
    """What we hold about a person, and nothing more (the list is in docs/security.md). One per user, made the first time
    anything asks for it (accounts.services.profile_of). Every field is blank until onboarding fills it in."""

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="profile")
    display_name = models.CharField(max_length=30, blank=True, validators=[validate_display_name],
                                    help_text="The name shown to other people. Chosen by the person, never their real name by default.")
    slack_id = models.CharField("Slack ID", max_length=12, blank=True, validators=[validate_slack_id],
                                help_text="The Slack member ID (U or W and capitals), not the username. Opens them in Slack.")
    region = models.CharField(max_length=2, blank=True, choices=REGIONS)
    timezone = models.CharField(max_length=64, blank=True, validators=[validate_timezone], help_text="An IANA name such as Asia/Kolkata.")
    expertise = models.CharField(max_length=10, blank=True, choices=EXPERTISE)
    onboarded_at = models.DateTimeField(null=True, blank=True, help_text="Set when they finish /welcome/. Until then they are sent there.")
    tutorial_done_at = models.DateTimeField(null=True, blank=True, help_text="Set when they finished or skipped the tutorial. Empty if the tutorial was switched off.")
    hackatime_connected = models.BooleanField(default=False, editable=False,
                                              help_text="Always False for now: the Hackatime connection is not built (accounts/hackatime.py).")

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["slack_id"], condition=~Q(slack_id=""), name="profile_slack_id_unique_when_set",
                                    violation_error_message="That Slack ID already belongs to somebody else."),
            models.CheckConstraint(
                condition=Q(onboarded_at__isnull=True) | (~Q(display_name="") & ~Q(slack_id="") & ~Q(region="") & ~Q(timezone="") & ~Q(expertise="")),
                name="profile_onboarded_means_filled_in",
                violation_error_message="A person is only onboarded once all five answers are filled in."),
        ]

    def __str__(self):
        return self.display_name or self.user.get_username()
