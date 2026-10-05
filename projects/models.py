"""Projects: the categories people pick from, Grandma's demands (the notes in her jar), the projects built around them and the
complaints people send her about new ones.

All of it is edited in the Django admin (projects/admin.py). Nothing here deals or charges: the draw is program/draw.py and
everything that changes a project is projects/services.py. Layers: program <- rules.py <- models.py <- services.py.
"""
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q

from accounts.public_id import new_public_id
from program.content.demands import LEVELS, TIERS
from program.draw import MAX_KEEP
from projects import rules
from projects.validators import validate_complaint_line, validate_complaint_text, validate_idea, validate_project_name


class Category(models.Model):
    """What sort of project it is. A demand lists the categories it can be dealt for."""

    slug = models.SlugField(unique=True)
    name = models.CharField(max_length=40, unique=True)
    sort = models.PositiveSmallIntegerField(default=100, help_text="Smaller comes first.")
    active = models.BooleanField(default=True, help_text="Off hides it from Talk to Grandma. Projects already in it keep it.")

    class Meta:
        ordering = ["sort", "name"]
        verbose_name_plural = "categories"

    def __str__(self):
        return self.name


class Subcategory(models.Model):
    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name="subcategories")
    name = models.CharField(max_length=40)
    sort = models.PositiveSmallIntegerField(default=100, help_text="Smaller comes first.")
    active = models.BooleanField(default=True, help_text="Off hides it from Talk to Grandma. Projects already in it keep it.")

    class Meta:
        ordering = ["category", "sort", "name"]
        verbose_name_plural = "subcategories"
        constraints = [models.UniqueConstraint(fields=["category", "name"], name="subcategory_name_unique_per_category")]

    def __str__(self):
        return f"{self.category}: {self.name}"


class Demand(models.Model):
    """One of Grandma's notes. The 28 starting ones were seeded from program/content (docs/projects.md); staff edit them here.
    The home page's fridge still reads the Python list, not this table."""

    name = models.CharField(max_length=40, unique=True)
    grandma_line = models.CharField(max_length=200, help_text="What Grandma says, in her voice.")
    rule = models.TextField(max_length=400, help_text="The proper plain-language rule, without her voice: what a reviewer checks.")
    tier = models.PositiveSmallIntegerField(choices=[(t, f"{t}: {LEVELS[t]}, \"{TIERS[t]}\"") for t in TIERS], default=1)
    categories = models.ManyToManyField(Category, blank=True, related_name="demands", help_text="The categories it can be dealt for.")
    excluded_subcategories = models.ManyToManyField(Subcategory, blank=True, related_name="excluded_demands",
                                                    help_text="Subcategories this demand can NOT be dealt for. It fits every subcategory of its categories except these. "
                                                              "For example Single File cannot be dealt to a Mobile app.")
    conflicts = models.ManyToManyField("self", blank=True, help_text="Demands that are never dealt in the same hand as this one. "
                                                                    "Saving one side adds the other.")
    active = models.BooleanField(default=True, help_text="Off takes it out of the jar. Projects already holding it keep it.")

    class Meta:
        ordering = ["tier", "name"]
        constraints = [models.CheckConstraint(condition=Q(tier__in=list(TIERS)), name="demand_tier_is_1_to_3")]

    def __str__(self):
        return self.name


class Project(models.Model):
    """What a person is building. Made by Talk to Grandma (never by hand) the moment the hand is dealt, so a project always
    comes after talking to her; it is `dealing` until they confirm the notes they keep, then `building`."""

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="projects")
    public_id = models.CharField(max_length=10, unique=True, editable=False, default=new_public_id,
                                 help_text="The random id in the project's public address (/p/<id>-<name>/), so the database number never shows. Made once, never changed.")
    name = models.CharField(max_length=40, validators=[validate_project_name])
    idea = models.CharField(max_length=200, validators=[validate_idea], help_text="What they said they would make.")
    category = models.ForeignKey(Category, on_delete=models.PROTECT, related_name="projects")
    subcategory = models.ForeignKey(Subcategory, on_delete=models.PROTECT, null=True, blank=True, related_name="projects")
    status = models.CharField(max_length=20, choices=rules.STATUSES, default=rules.DEALING)
    created_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True, blank=True, editable=False, help_text="When they confirmed their demands. Nothing counts down from here: a project has no time limit.")
    hand = models.JSONField(default=list, editable=False, help_text="The ids of the demands dealt. Saved on the project so a refresh never re-rolls.")
    redeals_used = models.PositiveSmallIntegerField(default=0, editable=False, help_text="Re-deals so far, free and paid.")
    demands = models.ManyToManyField(Demand, through="ProjectDemand", related_name="projects")
    tracked_names = models.JSONField(default=list, blank=True, editable=False,
                                     help_text="The Hackatime projects the person last checked their hours against (accounts/hackatime.py). Staff only.")
    tracked_seconds = models.PositiveIntegerField(null=True, blank=True, editable=False,
                                                  help_text="What Hackatime reported for that name between the start of the project and the check. Staff only: the person never sees it.")
    tracked_at = models.DateTimeField(null=True, blank=True, editable=False, help_text="When the check was made.")

    class Meta:
        ordering = ["-created_at", "-id"]
        constraints = [
            models.UniqueConstraint(fields=["user"], condition=Q(status__in=rules.WORKING_STATUSES), name="one_working_project_per_user",
                                    violation_error_message="That person already has a project in progress. Abandon it first."),
            models.CheckConstraint(condition=Q(status__in=[rules.DEALING, rules.ABANDONED]) | Q(started_at__isnull=False),
                                   name="project_started_unless_dealing_or_abandoned",
                                   violation_error_message="A project is only started in Talk to Grandma, when the person confirms their demands."),
        ]

    def __str__(self):
        return f"{self.name} ({self.user})"

    def clean(self):
        if self.category_id and self.subcategory_id and self.subcategory.category_id != self.category_id:
            raise ValidationError({"subcategory": "That subcategory belongs to a different category."})

    def validate_constraints(self, exclude=None):
        """Check every constraint even for fields a form leaves out: the admin shows `user` and `started_at` read only, and
        a constraint over a left-out field would otherwise be skipped and only fail in the database, as an error page."""
        super().validate_constraints(exclude=None)

    @property
    def active(self):
        return self.status in rules.ACTIVE_STATUSES


class ProjectDemand(models.Model):
    """A demand a person kept for their project (one to three), in the order they appear in the hand."""

    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="kept")
    demand = models.ForeignKey(Demand, on_delete=models.PROTECT, related_name="+")
    order = models.PositiveSmallIntegerField()

    class Meta:
        ordering = ["order"]
        constraints = [
            models.UniqueConstraint(fields=["project", "demand"], name="projectdemand_demand_once_per_project"),
            models.UniqueConstraint(fields=["project", "order"], name="projectdemand_order_once_per_project"),
            models.CheckConstraint(condition=Q(order__gte=1, order__lte=MAX_KEEP), name="projectdemand_order_within_the_keep_limit"),
        ]

    def __str__(self):
        return f"{self.project}: {self.demand}"


class Complaint(models.Model):
    """A person's suggestion for a new demand, sent at /complaints/. PRIVATE: only staff read it, in the admin (which also sets its status);
    no page, board or count of it is ever public. Made only by projects/complaints.py, which enforces the lengths and the daily limit."""

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="complaints")
    title = models.CharField(max_length=rules.TITLE_MAX, validators=[validate_complaint_line], help_text="The name of the demand they suggest.")
    text = models.CharField(max_length=rules.TEXT_MAX, validators=[validate_complaint_text], help_text="What Grandma should demand, and why it is annoying.")
    example = models.CharField(max_length=rules.EXAMPLE_MAX, blank=True, validators=[validate_complaint_line], help_text="A project it would fit, if they gave one.")
    created_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=10, choices=rules.COMPLAINT_STATUSES, default=rules.NEW)

    class Meta:
        ordering = ["-created_at", "-id"]

    def __str__(self):
        return self.title
