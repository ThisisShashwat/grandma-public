"""What a person hands in to Grandma, and what a reviewer decided about it.

A Submission belongs to a project and is one ROUND of handing it in: a project is handed in once, and again after each time a reviewer
asked for changes, up to the MAX_ROUNDS setting (docs/changes-requested-plan.md). The participant fields are written once, when they hand
it in, and never edited. The reviewer fields are set in the admin (docs/submissions.md) and frozen once the person has collected the
result. Layers: program <- rules.py, links.py <- models.py <- services.py.
"""
import uuid
from pathlib import Path

from django.conf import settings
from django.db import models
from django.db.models import Q

from projects.models import Project
from submissions import rules
from submissions.images import FORMATS
from submissions.validators import validate_prose, validate_repo_url, validate_web_url

ARI_KINDS = ("ingest", "withdraw")
ARI_STATUSES = ("pending", "sent", "failed")
EXTENSIONS = {f".{extension}" for extension, _ in FORMATS.values()}


def screenshot_path(instance, filename):
    """Where a screenshot is stored: always a random name made here, whatever the file was called (images.py already made one)."""
    extension = Path(filename).suffix.lower()
    return f"screenshots/{uuid.uuid4().hex}{extension if extension in EXTENSIONS else '.png'}"


class Submission(models.Model):
    project = models.ForeignKey(Project, on_delete=models.PROTECT, related_name="submissions")
    round = models.PositiveSmallIntegerField(default=1, help_text="Which time this project was handed in: 1 the first time, 2 after changes were asked for once, and so on.")
    status = models.CharField(max_length=20, choices=rules.STATUSES, default=rules.SUBMITTED)
    submitted_at = models.DateTimeField(auto_now_add=True)

    # what the person handed in (written once, never edited)
    hackatime_projects = models.JSONField(default=list, blank=True, editable=False,
                                          help_text="The Hackatime projects their hours were checked against, copied from the project when they handed in. "
                                                    "Empty when they made no check. Staff only.")
    tracked_seconds = models.PositiveIntegerField(null=True, blank=True, editable=False,
                                                  help_text="What Hackatime reported for it, copied from the project when they handed in. Staff only: the person never sees it.")
    tracked_at = models.DateTimeField(null=True, blank=True, editable=False, help_text="When that check was made.")
    tiers = models.JSONField(null=True, blank=True, editable=False,
                             help_text="The tiers of the demands they kept, frozen when they handed in: what this round pays is worked out from these, never from the live demands. "
                                       "Empty only on a round handed in before this was kept (the live tiers are used then). Staff only.")
    repo_url = models.URLField(max_length=300, validators=[validate_repo_url])
    playable_url = models.URLField(max_length=300, validators=[validate_web_url],
                                   help_text="Where anyone can try it. Not on a host that falls asleep (the BLOCKED_HOSTS setting).")
    description = models.TextField(max_length=1500, validators=[validate_prose])
    screenshot = models.ImageField(upload_to=screenshot_path, max_length=100)
    recording_url = models.URLField(max_length=300, blank=True, validators=[validate_web_url], help_text="A link to a short recording. No video is uploaded.")
    declarations = models.JSONField(default=list, help_text="The keys of the boxes they ticked (the SUBMISSION_CHECKS setting).")
    ai_declaration_text = models.TextField(max_length=1000, blank=True, validators=[validate_prose], help_text="What they used AI for, in their words.")

    # what the reviewer decided (the admin's Review form; frozen once claimed)
    approved_hours = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True,
                                         help_text=f"The hours that count, 0 to {rules.MAX_HOURS}. Your own number: Hackatime's figure above is evidence, it is never copied here. "
                                                   "Never shown to the person: they see cookies only.")
    quality = models.BooleanField(default=False, help_text="Grandma loved it: the quality bonus.")
    ribbon = models.BooleanField(default=False, help_text="A Blue Ribbon project.")
    public_note = models.TextField(max_length=1000, blank=True, help_text="What Grandma tells the person, in her voice. The person reads this. Never put anything private in it.")
    internal_note = models.TextField(max_length=2000, blank=True, help_text="For staff only. Never shown to the person.")
    reviewed_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, editable=False, on_delete=models.PROTECT, related_name="+")
    reviewed_at = models.DateTimeField(null=True, blank=True, editable=False)
    cookies_awarded = models.PositiveIntegerField(null=True, blank=True, editable=False, help_text="Worked out when the review was saved. What Grandma hands over.")
    claimed_at = models.DateTimeField(null=True, blank=True, editable=False, help_text="When Grandma handed the result over. After this the review is frozen.")

    # Ari (HQ's review tool, submissions/ari.py): where the ship sits there and what its reviewer decided. Staff only.
    ari_ship_id = models.CharField(max_length=40, blank=True, editable=False, help_text="Ari's id for this hand-in (like AR-4821), from its answer when it took the ship.")
    reviewer_label = models.CharField(max_length=254, blank=True, editable=False, help_text="Who decided it in Ari: the reviewer's email or Slack id, as text. Staff only. Empty for a decision made in this admin.")
    demand_checks = models.JSONField(default=list, blank=True, editable=False, help_text="What the Ari reviewer ticked for each demand the person kept: a list of demand id and met.")
    ari_justification = models.JSONField(default=dict, blank=True, editable=False,
                                         help_text="What the Ari reviewer wrote to back the hours: the Hackatime projects with their dates, the Hackatime id, timelapse links, the technical features and why hours were cut. "
                                                   "Kept for HQ's audit. PRIVATE: staff only, never on a page, never shown to the person.")
    needs_staff = models.BooleanField(default=False, editable=False,
                                      help_text="Ari sent something this site could not apply by itself (hours too big or missing, a decision after the person collected, a revert after they spent the cookies). "
                                                "Look at it, fix it by hand if needed, then clear this with the admin action.")

    taken_down_at = models.DateTimeField(null=True, blank=True, editable=False,
                                         help_text="Staff took this round off every public page and deleted its screenshot (services.take_down). Staff only. The person's own pages are unchanged.")

    class Meta:
        ordering = ["-submitted_at", "-id"]
        constraints = [
            models.CheckConstraint(condition=Q(status__in=[s for s, _ in rules.STATUSES]), name="submission_status_is_known"),
            models.UniqueConstraint(fields=["project", "round"], name="submission_one_per_round",
                                    violation_error_message="That project has already handed in that round."),
            models.CheckConstraint(condition=Q(round__gte=1, round__lte=rules.MAX_ROUND_LIMIT), name="submission_round_is_sane",
                                   violation_error_message=f"The round must be between 1 and {rules.MAX_ROUND_LIMIT}."),
            models.CheckConstraint(condition=Q(claimed_at__isnull=True) | Q(status__in=rules.REVIEWED), name="submission_claimed_only_after_review"),
            models.CheckConstraint(condition=~Q(status=rules.APPROVED) | Q(approved_hours__isnull=False), name="submission_approved_has_hours",
                                   violation_error_message="An approved submission needs its approved hours (0 pays nothing)."),
            models.CheckConstraint(condition=Q(approved_hours__isnull=True) | Q(approved_hours__gte=0, approved_hours__lte=rules.MAX_HOURS),
                                   name="submission_hours_are_sane", violation_error_message=f"Hours must be between 0 and {rules.MAX_HOURS}."),
        ]

    def __str__(self):
        return f"{self.project.name} ({self.get_status_display().lower()})"

    @property
    def reviewed(self):
        return self.status in rules.REVIEWED

    @property
    def claimed(self):
        return self.claimed_at is not None

    def validate_constraints(self, exclude=None):
        """Check every constraint even for fields a form leaves out (the admin shows most of them read only): a constraint over a
        left-out field would otherwise be skipped and only fail in the database, as an error page."""
        super().validate_constraints(exclude=None)


class AriDelivery(models.Model):
    """One message to Ari that must get there: a ship (ingest) or the withdrawal of an open one. The exact bytes are kept, so a resend is byte for byte
    the same and Ari answers 200 duplicate within the hour (submissions/ari.py). Never holds a secret, and last_error is always one of a few fixed words."""
    submission = models.ForeignKey(Submission, on_delete=models.PROTECT, related_name="ari_deliveries")
    kind = models.CharField(max_length=10, choices=[(k, k) for k in ARI_KINDS])
    body = models.BinaryField(editable=False)
    status = models.CharField(max_length=10, choices=[(s, s) for s in ARI_STATUSES], default="pending")
    attempts = models.PositiveSmallIntegerField(default=0)
    last_status = models.PositiveSmallIntegerField(null=True, blank=True, help_text="The HTTP status Ari last answered with.")
    last_error = models.CharField(max_length=40, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    sent_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["id"]
        constraints = [
            models.CheckConstraint(condition=Q(kind__in=ARI_KINDS), name="ari_delivery_kind_is_known"),
            models.CheckConstraint(condition=Q(status__in=ARI_STATUSES), name="ari_delivery_status_is_known"),
            models.CheckConstraint(condition=Q(attempts__gte=0), name="ari_delivery_attempts_not_negative"),
        ]

    def __str__(self):
        return f"{self.kind} of {self.submission_id} ({self.status})"


class AriEvent(models.Model):
    """One message Ari sent us, written when it is handled: the delivery id is unique, so Ari's retry of the same delivery is a no-op."""
    delivery_id = models.CharField(max_length=64, unique=True)
    event = models.CharField(max_length=40)
    external_id = models.CharField(max_length=100, blank=True)
    received_at = models.DateTimeField(auto_now_add=True)
    outcome = models.CharField(max_length=20, blank=True, help_text="What this site did with it: applied, noop, ignored, refused, reverted or needs_staff.")

    class Meta:
        ordering = ["-id"]
