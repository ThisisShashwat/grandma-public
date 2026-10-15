"""The staff side of submissions: a minimal way to look at what was handed in and set an outcome (status, approved hours, the quality
and ribbon bonuses, a note Grandma reads out and a private one). The real reviewing flow is the owner's, still to come. What the
person handed in is read only, and so is the whole review once Grandma has handed the result over (a correction after that is a
ledger adjustment). Nothing can be added or deleted here: a submission is made by the person, and kept."""
from django import forms
from django.contrib import admin
from django.core.exceptions import PermissionDenied, ValidationError
from django.utils import timezone
from django.utils.html import format_html, format_html_join

from pages.live import live
from program.content.demands import LEVELS
from projects import services as project_services
from submissions import rules, services
from submissions.models import Submission

PARTICIPANT = ("project", "round", "owner", "submitted_at", "hackatime_project", "hackatime_says", "repo_link", "playable_link", "description", "screenshot_preview",
               "recording_link", "ticked", "ai_declaration_text", "kept_notes")
REVIEW = ("status", "approved_hours", "quality", "ribbon", "public_note", "internal_note")
RESULT = ("cookies_preview", "reviewed_by", "reviewed_at", "cookies_awarded", "claimed_at")
ARI = ("ari_ship_id", "reviewer_label", "demand_checks", "needs_staff")        # what Ari (HQ's review tool) said, all read only (submissions/ari_inbound.py)


class TakenDownFilter(admin.SimpleListFilter):
    title = "taken down"
    parameter_name = "taken_down"

    def lookups(self, request, model_admin):
        return (("yes", "Yes"), ("no", "No"))

    def queryset(self, request, queryset):
        return queryset.filter(taken_down_at__isnull=self.value() == "no") if self.value() in ("yes", "no") else queryset


class ReviewForm(forms.ModelForm):
    """The Review form: the status says "Ask for changes" for what the person hears as changes requested, and the decision is checked
    with the same rule as services.review (a note, and not on the last round, and never on your own project). `max_rounds` and `reviewer`
    (the signed-in user's id) are set once per request by get_form."""
    max_rounds = 1
    reviewer = None

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if "status" in self.fields:
            self.fields["status"].choices = rules.REVIEW_CHOICES

    def clean(self):
        cleaned = super().clean()
        if self.instance.project.user_id == self.reviewer:
            raise ValidationError(services.OWN_PROJECT)
        if "status" in cleaned and "public_note" in cleaned:
            problem = rules.review_problem(cleaned["status"], cleaned["public_note"], self.instance.round, self.max_rounds, was=self.initial.get("status", ""))
            if problem:
                raise ValidationError(problem)
        return cleaned


@admin.register(Submission)
class SubmissionAdmin(admin.ModelAdmin):
    form = ReviewForm
    list_display = ("project", "round", "owner", "status", "submitted_at", "cookies_awarded", "collected", "needs_staff", "taken_down")
    list_filter = ("status", "needs_staff", TakenDownFilter, "project__category")
    actions = ["clear_needs_staff", "take_down", "lift_takedown"]
    list_select_related = ("project", "project__user", "reviewed_by")
    search_fields = ("project__name", "project__user__username")
    fieldsets = (
        ("What they handed in", {"fields": PARTICIPANT}),
        ("Review", {"fields": REVIEW, "description": "Set the status and, for an approval, the hours that count. Ask for changes needs a public note that says what "
                                                     "to change (it is public, like Grandma's other notes), and cannot be used on the last round. Reject is final: for cheating or spam. "
                                                     "Grandma tells the person the public note in her voice and hands over the cookies when they next visit. "
                                                     "The person never sees the internal note. Once they have collected, the approved hours and the tracked time are public, in words, on the project page. The hours are your own number: what Hackatime says (above) is evidence, never filled in for you. "
                                                     "Personal details (a name, an address, a face) or spam in a hand-in are a takedown, not Ask for changes and not Reject: use the list action Take down, which hides the round from every public page and deletes its screenshot."}),
        ("Result", {"fields": RESULT}),
        ("Takedown", {"fields": ("taken_down_at",), "description": "Set by the list actions Take down and Lift takedown, never typed here. While it is set the round is on no public page. Lifting it does not bring the screenshot back: that file is deleted."}),
        ("Ari", {"fields": ARI, "description": "Filled by Ari's decisions (never typed here). Needs staff means Ari sent something this site did not apply by itself (a revert, a decision "
                                               "after the person collected, bad hours, a failed fraud check): look at it, decide it in the Review form if it must be decided, then "
                                               "clear the flag with the list action. While it is set, nothing more from Ari is applied to this submission."}),
        ("What Ari's reviewer wrote to back the hours (private)", {"fields": ("justification",), "classes": ("collapse",),
                                                                  "description": "Kept for HQ's audit. Staff only: never shown to the person, never on a public page."}),
    )
    readonly_fields = PARTICIPANT + RESULT + ARI + ("justification", "taken_down_at")

    def has_change_permission(self, request, obj=None):
        """Once the person has collected, the whole result is frozen: it opens view only, and a form opened earlier is a 403 when posted (no success message)."""
        return super().has_change_permission(request, obj) and not (obj is not None and obj.claimed)

    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        form.max_rounds = live().MAX_ROUNDS
        form.reviewer = request.user.pk
        return form

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def save_model(self, request, obj, form, change):
        if not form.has_changed():
            return
        try:
            services.review(obj, by=request.user, max_rounds=form.max_rounds)
        except (services.AlreadyCollected, ValidationError):
            raise PermissionDenied from None        # only a race gets here (the form checks the same rules): nothing is saved, and the admin writes no success message or log entry
        self.message_user(request, saved_message(obj))

    @admin.action(description="Clear the needs staff flag", permissions=["change"])
    def clear_needs_staff(self, request, queryset):
        """Staff looked at what Ari sent: take the flag off the chosen submissions (services.clear_needs_staff writes the audit entry, once each)."""
        cleared = sum(services.clear_needs_staff(pk, by=request.user) for pk in queryset.filter(needs_staff=True).values_list("pk", flat=True))
        self.message_user(request, f"Cleared the flag on {cleared} submission{'' if cleared == 1 else 's'}.")

    @admin.action(description="Take down (hide from public pages and delete the screenshot)", permissions=["change"])
    def take_down(self, request, queryset):
        """Staff pulled these rounds off every public page and deleted their screenshots (services.take_down audits each, once). Allowed on a collected round too: it is no review change."""
        done = sum(services.take_down(submission, by=request.user) for submission in queryset)
        self.message_user(request, f"{done} round{'' if done == 1 else 's'} taken down.")

    @admin.action(description="Lift takedown (put back on the public pages, the screenshot stays deleted)", permissions=["change"])
    def lift_takedown(self, request, queryset):
        done = sum(services.lift_takedown(submission, by=request.user) for submission in queryset)
        self.message_user(request, f"{done} round{'' if done == 1 else 's'} put back on the public pages.")

    # the list and the read only parts of the form

    @admin.display(description="taken down", boolean=True, ordering="taken_down_at")
    def taken_down(self, obj):
        return obj.taken_down_at is not None

    @admin.display(description="person", ordering="project__user__username")
    def owner(self, obj):
        return obj.project.user.get_username()

    @admin.display(description="collected", boolean=True)
    def collected(self, obj):
        return obj.claimed

    @admin.display(description="Hackatime project")
    def hackatime_project(self, obj):
        return ", ".join(obj.hackatime_projects) or "none"

    @admin.display(description="Hackatime says")
    def hackatime_says(self, obj):
        """Evidence for the reviewer, never a figure for the person: the seconds Hackatime counted for the project when they handed it in. approved_hours is still
        the reviewer's own number (nothing is copied or prefilled from this)."""
        if obj.tracked_seconds is None:
            return "no Hackatime check"
        return f"{obj.tracked_seconds / 3600:.2f} hours (checked at {timezone.localtime(obj.tracked_at):%Y-%m-%d %H:%M %Z})"

    @admin.display(description="justification")
    def justification(self, obj):
        """Ari's `review.justification` as stored (submissions/ari_inbound.py justification_of), one line per part; format_html escapes every value."""
        return format_html("<dl>{}</dl>", format_html_join("", "<dt><b>{}</b></dt><dd>{}</dd>", obj.ari_justification.items())) if obj.ari_justification else "none"

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


def saved_message(obj):
    if obj.status == rules.SUBMITTED:
        return "Saved. It is back to handed in, with nothing awarded."
    if obj.status == rules.CHANGES_REQUESTED:
        return f"Saved. Grandma will read the note to {obj.project.user} when they next talk to her, and they can fix it and hand it in again. No cookies."
    return f"Saved. {obj.cookies_awarded or 0} cookies will be handed over when {obj.project.user} next talks to Grandma."


def link(url):
    return format_html('<a href="{0}" target="_blank" rel="noopener noreferrer">{0}</a>', url)
