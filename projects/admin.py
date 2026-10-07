"""The staff side of projects. Categories, subcategories and demands are edited here (they were seeded once from program/content;
the database is the truth from then on). A project cannot be made here: only Talk to Grandma makes one, so it always comes after
talking to her. Staff can read every project and abandon one, which frees its owner to start another. Complaints (suggestions for new
demands) are read here, by staff only, and their status is the one thing staff set."""
from django.contrib import admin
from django.db import transaction

from audit import services as audit
from projects import rules, services
from projects.models import Category, Complaint, Demand, Project, ProjectDemand, Subcategory, Suggestion
from projects.signals import project_abandoned


class SubcategoryInline(admin.TabularInline):
    model = Subcategory
    extra = 1


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "sort", "active", "demands_in_jar")
    list_editable = ("sort", "active")
    prepopulated_fields = {"slug": ("name",)}
    inlines = [SubcategoryInline]

    @admin.display(description="active demands")
    def demands_in_jar(self, obj):
        return obj.demands.filter(active=True).count()


@admin.register(Subcategory)
class SubcategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "category", "sort", "active")
    list_filter = ("category", "active")
    search_fields = ("name",)


@admin.register(Demand)
class DemandAdmin(admin.ModelAdmin):
    list_display = ("name", "tier", "fits", "clashes_with", "active")
    list_filter = ("tier", "active", "categories")
    search_fields = ("name", "grandma_line", "rule")
    filter_horizontal = ("categories", "excluded_subcategories", "conflicts")
    fields = ("name", "grandma_line", "rule", "tier", "categories", "excluded_subcategories", "conflicts", "active")

    def get_queryset(self, request):
        return super().get_queryset(request).prefetch_related("categories", "conflicts", "excluded_subcategories")

    def formfield_for_manytomany(self, db_field, request, **kwargs):
        """A subcategory is listed as 'Category: name', so fetch the category with it (one query, not one per choice)."""
        if db_field.name == "excluded_subcategories":
            kwargs["queryset"] = Subcategory.objects.select_related("category")
        return super().formfield_for_manytomany(db_field, request, **kwargs)

    @admin.display(description="fits")
    def fits(self, obj):
        """Its categories, each with the subcategories it can not be dealt for: 'Web (not Browser extension), Software (not Mobile app)'."""
        skipped = {}
        for sub in obj.excluded_subcategories.all():
            skipped.setdefault(sub.category_id, []).append(sub.name)
        return ", ".join(c.name + (f" (not {', '.join(skipped[c.id])})" if c.id in skipped else "") for c in obj.categories.all())

    @admin.display(description="never with")
    def clashes_with(self, obj):
        return ", ".join(d.name for d in obj.conflicts.all())


class KeptInline(admin.TabularInline):
    """The demands the person kept. Read only: they are chosen in the conversation, one to three, and never edited by hand."""
    model = ProjectDemand
    extra = 0
    fields = ("order", "demand")
    readonly_fields = ("order", "demand")
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ("name", "user", "category", "status", "started_at", "redeals_used")
    list_filter = ("status", "category")
    search_fields = ("name", "user__username", "idea")
    list_select_related = ("user", "category")
    inlines = [KeptInline]
    actions = ["abandon"]
    fields = ("user", "name", "idea", "category", "subcategory", "status", "created_at", "started_at", "dealt", "redeals_used")
    readonly_fields = ("user", "created_at", "started_at", "dealt", "redeals_used")

    def has_add_permission(self, request):
        return False

    def save_model(self, request, obj, form, change):
        """The change form can set the status by hand, so a changed status is audited (inside the admin's own transaction, with the save)."""
        old_status = form.initial.get("status")
        super().save_model(request, obj, form, change)
        if "status" in form.changed_data:
            audit.record("project.admin_status", actor=request.user, subject=obj.user, target=obj, details={"from": old_status, "to": obj.status})

    @admin.display(description="demands dealt (the hand)")
    def dealt(self, obj):
        return ", ".join(d.name for d in services.hand_demands(obj)) or "-"

    @admin.action(description="Abandon (frees the person to start another project)", permissions=["change"])
    def abandon(self, request, queryset):
        count = 0
        for project in queryset.filter(status__in=rules.ACTIVE_STATUSES).select_related("user"):
            with transaction.atomic():
                old_status = project.status
                project.status = rules.ABANDONED
                project.save(update_fields=["status"])
                audit.record(
                    "project.abandon",
                    actor=request.user,
                    subject=project.user,
                    target=project,
                    details={"from": old_status},
                )
                project_abandoned.send(sender=Project, project=project)
            count += 1
        self.message_user(request, f"Abandoned {count} projects.")


@admin.register(Complaint)
class ComplaintAdmin(admin.ModelAdmin):
    """What a person typed is read only, and nothing can be added or deleted: a complaint is made only by the person (projects/complaints.py)
    and kept. Staff set the status, here or in the list."""
    list_display = ("created_at", "user", "title", "status")
    list_editable = ("status",)
    list_filter = ("status",)
    list_select_related = ("user",)
    search_fields = ("title", "text")
    fields = ("user", "title", "text", "example", "created_at", "status")
    readonly_fields = ("user", "title", "text", "example", "created_at")

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def save_model(self, request, obj, form, change):
        """A changed status is audited, inside the admin's own transaction, with the save."""
        old_status = form.initial.get("status")
        super().save_model(request, obj, form, change)
        if "status" in form.changed_data:
            audit.record("complaint.admin_status", actor=request.user, subject=obj.user, target=obj, details={"from": old_status, "to": obj.status})


@admin.register(Suggestion)
class SuggestionAdmin(admin.ModelAdmin):
    """The suggestion board (projects/suggestions.py), highest votes first. What people typed and the votes are read only; staff hide a suggestion (off the
    board, kept) or delete it once they have added the real demand or Pantry item by hand. Nothing can be added here: only a person suggests."""
    list_display = ("title", "kind", "votes", "hidden", "created_at", "user")
    list_editable = ("hidden",)
    list_filter = ("kind", "hidden")
    list_select_related = ("user",)
    search_fields = ("title", "text")
    ordering = ("-votes", "-created_at")
    fields = ("kind", "title", "text", "example", "votes", "user", "created_at", "hidden")
    readonly_fields = ("kind", "title", "text", "example", "votes", "user", "created_at")
    actions = ("hide", "show")

    def has_add_permission(self, request):
        return False

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        if "hidden" in form.changed_data:
            audit.record("suggestion.admin_hidden", actor=request.user, subject=obj.user, target=obj, details={"hidden": obj.hidden})

    def delete_model(self, request, obj):
        audit.record("suggestion.admin_delete", actor=request.user, subject=obj.user, target=obj, details={"suggestion": obj.pk, "votes": obj.votes})
        super().delete_model(request, obj)

    def delete_queryset(self, request, queryset):
        for obj in queryset:
            self.delete_model(request, obj)

    @admin.action(description="Hide from the board")
    def hide(self, request, queryset):
        self.set_hidden(request, queryset, True)

    @admin.action(description="Show on the board again")
    def show(self, request, queryset):
        self.set_hidden(request, queryset, False)

    def set_hidden(self, request, queryset, hidden):
        with transaction.atomic():
            for obj in queryset.exclude(hidden=hidden):
                obj.hidden = hidden
                obj.save(update_fields=["hidden"])
                audit.record("suggestion.admin_hidden", actor=request.user, subject=obj.user, target=obj, details={"hidden": hidden})
