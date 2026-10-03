"""What a person hands in to Grandma, and what a reviewer decided about it.

A Submission belongs to a project. Software has exactly one ship (stage is empty). Hardware has a design ship and then a build
ship, one of each at most, the build only after the design was approved and the person has heard it from Grandma. The participant
fields are written once, when they hand it in, and never edited. The reviewer fields are set in the admin (docs/submissions.md) and
frozen once the person has collected the result. Layers: program <- rules.py, links.py <- models.py <- services.py.
"""
import uuid
from pathlib import Path

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q

from projects.models import Category, Project
from submissions import rules
from submissions.images import FORMATS
from submissions.validators import validate_prose, validate_repo_url, validate_web_url

EXTENSIONS = {f".{extension}" for extension, _ in FORMATS.values()}


def screenshot_path(instance, filename):
    """Where a screenshot is stored: always a random name made here, whatever the file was called (images.py already made one)."""
    extension = Path(filename).suffix.lower()
    return f"screenshots/{uuid.uuid4().hex}{extension if extension in EXTENSIONS else '.png'}"


class Submission(models.Model):
    project = models.ForeignKey(Project, on_delete=models.PROTECT, related_name="submissions")
    stage = models.CharField(max_length=6, choices=rules.STAGES, null=True, blank=True,
                             help_text="Hardware only: the design ship, then the build ship. Empty for software, which has one ship.")
    status = models.CharField(max_length=9, choices=rules.STATUSES, default=rules.SUBMITTED)
    submitted_at = models.DateTimeField(auto_now_add=True)

    # what the person handed in (written once, never edited)
    hackatime_project = models.CharField(max_length=100, null=True, blank=True, editable=False,
                                         help_text="STUB. The Hackatime project their hours come from, filled in when Hackatime is connected "
                                                   "(accounts/hackatime.py). Nothing sets it yet.")
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
                                         help_text=f"The hours that count, 0 to {rules.MAX_HOURS}. Never shown to the person: they see cookies only.")
    quality = models.BooleanField(default=False, help_text="Grandma loved it: the quality bonus.")
    ribbon = models.BooleanField(default=False, help_text="A Blue Ribbon project.")
    public_note = models.TextField(max_length=1000, blank=True, help_text="What Grandma tells the person, in her voice. The person reads this. Never put anything private in it.")
    internal_note = models.TextField(max_length=2000, blank=True, help_text="For staff only. Never shown to the person.")
    reviewed_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, editable=False, on_delete=models.PROTECT, related_name="+")
    reviewed_at = models.DateTimeField(null=True, blank=True, editable=False)
    cookies_awarded = models.PositiveIntegerField(null=True, blank=True, editable=False, help_text="Worked out when the review was saved. What Grandma hands over.")
    claimed_at = models.DateTimeField(null=True, blank=True, editable=False, help_text="When Grandma handed the result over. After this the review is frozen.")

    class Meta:
        ordering = ["-submitted_at", "-id"]
        constraints = [
            models.CheckConstraint(condition=Q(status__in=[s for s, _ in rules.STATUSES]), name="submission_status_is_known"),
            models.CheckConstraint(condition=Q(stage__isnull=True) | Q(stage__in=[rules.DESIGN, rules.BUILD]), name="submission_stage_is_known"),
            models.UniqueConstraint(fields=["project", "stage"], name="submission_one_per_project_and_stage",
                                    violation_error_message="That project has already handed in that ship."),
            models.UniqueConstraint(fields=["project"], condition=Q(stage__isnull=True), name="submission_software_has_one_ship",
                                    violation_error_message="That project has already handed in its one ship."),
            models.CheckConstraint(condition=Q(claimed_at__isnull=True) | Q(status__in=rules.REVIEWED), name="submission_claimed_only_after_review"),
            models.CheckConstraint(condition=~Q(status=rules.APPROVED) | Q(approved_hours__isnull=False), name="submission_approved_has_hours",
                                   violation_error_message="An approved submission needs its approved hours (0 pays nothing)."),
            models.CheckConstraint(condition=Q(approved_hours__isnull=True) | Q(approved_hours__gte=0, approved_hours__lte=rules.MAX_HOURS),
                                   name="submission_hours_are_sane", violation_error_message=f"Hours must be between 0 and {rules.MAX_HOURS}."),
        ]

    def __str__(self):
        return f"{self.project.name}, {rules.STAGE_LABELS[self.stage].lower()} ({self.get_status_display().lower()})"

    @property
    def reviewed(self):
        return self.status in rules.REVIEWED

    @property
    def claimed(self):
        return self.claimed_at is not None

    def clean(self):
        """A software project's ship has no stage, a hardware project's has one."""
        if self.project_id and (self.stage is None) == (self.project.category.kind == Category.Kind.HARDWARE):
            raise ValidationError("Hardware ships are a design or a build; software has one ship and no stage.")

    def validate_constraints(self, exclude=None):
        """Check every constraint even for fields a form leaves out (the admin shows most of them read only): a constraint over a
        left-out field would otherwise be skipped and only fail in the database, as an error page."""
        super().validate_constraints(exclude=None)
