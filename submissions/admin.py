"""The staff side of submissions: a minimal way to look at what was handed in and set an outcome (status, approved hours, the quality
and ribbon bonuses, a note Grandma reads out and a private one). The real reviewing flow is the owner's, still to come. What the
person handed in is read only, and so is the whole review once Grandma has handed the result over (a correction after that is a
ledger adjustment). Nothing can be added or deleted here: a submission is made by the person, and kept."""
from django.contrib import admin, messages
from django.utils.html import format_html, format_html_join

from program.content.demands import LEVELS
from projects import services as project_services
from submissions import services
from submissions.models import Submission

PARTICIPANT = ("project", "owner", "submitted_at", "hackatime_project", "repo_link", "playable_link", "description", "screenshot_preview",
               "recording_link", "ticked", "ai_declaration_text", "kept_notes")
REVIEW = ("status", "approved_hours", "quality", "ribbon", "public_note", "internal_note")
RESULT = ("cookies_preview", "reviewed_by", "reviewed_at", "cookies_awarded", "claimed_at")


@admin.register(Submission)
class SubmissionAdmin(admin.ModelAdmin):
    list_display = ("project", "owner", "status", "submitted_at", "cookies_awarded", "collected")
    list_filter = ("status", "project__category")
    list_select_related = ("project", "project__user", "reviewed_by")
    search_fields = ("project__name", "project__user__username")
    fieldsets = (
        ("What they handed in", {"fields": PARTICIPANT}),
        ("Review", {"fields": REVIEW, "description": "Set the status and, for an approval, the hours that count. Grandma tells the person the public note in her "
                                                     "voice and hands over the cookies when they next visit. The person never sees the hours or the internal note."}),
        ("Result", {"fields": RESULT}),
    )
    readonly_fields = PARTICIPANT + RESULT

    def get_readonly_fields(self, request, obj=None):
        """Once the person has collected, the review is frozen too."""
        return self.readonly_fields + (REVIEW if obj is not None and obj.claimed else ())

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def save_model(self, request, obj, form, change):
        if not form.has_changed():
            return
        try:
            services.review(obj, by=request.user)
        except services.AlreadyCollected:
            self.message_user(request, "Grandma has already handed this one over, so it cannot be changed. A correction is a cookie ledger adjustment.", messages.ERROR)
            return
        self.message_user(request, f"Saved. {obj.cookies_awarded or 0} cookies will be handed over when {obj.project.user} next talks to Grandma."
                          if obj.reviewed else "Saved. It is back to handed in, with nothing awarded.")

    # the list and the read only parts of the form

    @admin.display(description="person", ordering="project__user__username")
    def owner(self, obj):
        return obj.project.user.get_username()

    @admin.display(description="collected", boolean=True)
    def collected(self, obj):
        return obj.claimed

    @admin.display(description="repository")
    def repo_link(self, obj):
        return link(obj.repo_url)

    @admin.display(description="playable link")
    def playable_link(self, obj):
        return link(obj.playable_url)

    @admin.display(description="recording")
    def recording_link(self, obj):
        return link(obj.recording_url) if obj.recording_url else "none"

    @admin.display(description="screenshot")
    def screenshot_preview(self, obj):
        return format_html('<a href="{0}" target="_blank" rel="noopener noreferrer"><img src="{0}" alt="Their screenshot" style="max-width: 24rem; max-height: 16rem"></a>',
                           obj.screenshot.url) if obj.screenshot else "none"

    @admin.display(description="boxes they ticked")
    def ticked(self, obj):
        return ", ".join(obj.declarations) or "none"

    @admin.display(description="the demands they kept")
    def kept_notes(self, obj):
        kept = project_services.kept_demands(obj.project)
        return format_html("<ul>{}</ul>", format_html_join("", "<li><b>{}</b> ({}): {}</li>", ((d.name, LEVELS[d.tier], d.rule) for d in kept)))

    @admin.display(description="cookies this review pays")
    def cookies_preview(self, obj):
        if not obj.reviewed:
            return "Nothing yet: set a status and save."
        return f"{services.cookies_for(obj)} (worked out from the saved review and the demands they kept; it is recomputed when you save)"


def link(url):
    return format_html('<a href="{0}" target="_blank" rel="noopener noreferrer">{0}</a>', url)
