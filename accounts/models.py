from django.conf import settings
from django.db import models
from django.db.models import Q

from accounts.public_id import new_public_id
from accounts.validators import validate_display_name, validate_slack_id, validate_timezone
from program.content.expertise import EXPERTISE
from program.content.regions import REGIONS

FILLED_IN = ("display_name", "slack_id", "region", "timezone", "expertise")


class Profile(models.Model):
    """What we hold about a person, and nothing more (the list is in docs/security.md). One per user, made the first time
    anything asks for it (accounts.services.profile_of). Every field is blank until onboarding fills it in."""

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="profile")
    public_id = models.CharField(max_length=10, unique=True, editable=False, default=new_public_id,
                                 help_text="The random id in the person's public address (/u/<id>-<name>/), so the database number never shows. Made once, never changed.")
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
                                              help_text="True once they have connected a Hackatime account. Only the connect callback sets it (accounts/hackatime.py).")
    hackatime_user_id = models.CharField("Hackatime user ID", max_length=40, null=True, blank=True, unique=True, editable=False,
                                         help_text="The id of the Hackatime account they connected, so one Hackatime account backs only one account here. Only the connect callback "
                                                   "sets it. Nothing else about them is kept from Hackatime except the encrypted token below.")
    hackatime_token = models.TextField(blank=True, default="", editable=False,
                                       help_text="The Hackatime access token, ENCRYPTED with the keys in HACKATIME_TOKEN_KEYS. Empty when they have not connected or the token was dropped. Only accounts/hackatime.py reads or writes it; it is never shown anywhere.")
    hca_sub = models.CharField("Hack Club Auth ID", max_length=100, null=True, blank=True, unique=True, editable=False,
                               help_text="The stable id Hack Club Auth gives this person (its sub claim). The first Hack Club sign-in makes the account and sets it "
                                         "(accounts/hca.py). Nothing else about them is kept from Hack Club.")
    hca_checked_at = models.DateTimeField(null=True, blank=True, editable=False, help_text="The last time they signed in with Hack Club.")
    beta_access = models.BooleanField(default=False, help_text="May use the participant pages while the BETA_MODE setting is on. Staff never need it. "
                                                               "New profiles start without it; the migration gave it to everyone who was here before.")

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
