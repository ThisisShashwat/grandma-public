from constance.admin import Config, ConstanceAdmin
from django.contrib import admin, messages
from django.contrib.auth import get_user_model
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from accounts import switches
from accounts.models import Profile
from accounts.services import set_beta_access, unlink_hackatime
from pages.live import live

User = get_user_model()


class ProfileInline(admin.StackedInline):
    model = Profile
    can_delete = False
    max_num = 1
    # hackatime_token is editable=False and omitted here on purpose: it must never appear in the admin.
    readonly_fields = ("hackatime_connected", "hackatime_user_id", "hca_sub", "hca_checked_at", "beta_access")        # the Hack Club fields are set only by the sign-in (accounts/hca.py), the Hackatime ones only by the connect callback (accounts/hackatime.py); beta access is given under Profiles, where every change is recorded



class UserAdmin(BaseUserAdmin):
    """Django's user admin plus the Profile. Accounts are made by the first Hack Club sign-in (accounts/hca.py),
    staff are given the `is_staff` tick by hand in the admin (docs/owner.md 2026-10-05), a development account can still
    be made in the admin, and the person fills in the rest at /welcome/."""
    inlines = [ProfileInline]

    def get_inline_instances(self, request, obj=None):
        return super().get_inline_instances(request, obj) if obj else []        # nothing to show on the add page


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    """Who is let in while BETA_MODE is on. The only thing edited here is beta access, by hand or with the two actions, and every change is
    recorded in the audit log (accounts.services.set_beta_access). One more action clears a Hackatime link (the only way to undo
    one), also recorded. Profiles are made by the site, never here, and not deleted here."""
    list_display = ("user", "display_name", "slack_id", "beta_access", "staff")
    list_filter = ("beta_access", "user__is_staff")
    search_fields = ("user__username", "display_name", "slack_id")
    list_select_related = ("user",)
    ordering = ("user__username",)
    actions = ["give_access", "take_access_away", "unlink_hackatime_account"]
    # hackatime_token is editable=False and omitted here on purpose: it must never appear in the admin.
    fields = ("user", "display_name", "slack_id", "email", "region", "timezone", "expertise", "onboarded_at", "tutorial_done_at", "beta_access")        # the email is on the detail page only (staff need it to talk to Ari), never a list column or a search field
    readonly_fields = tuple(name for name in fields if name != "beta_access")


    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    @admin.display(boolean=True, description="staff (never need it)")
    def staff(self, obj):
        return obj.user.is_staff or obj.user.is_superuser

    def save_model(self, request, obj, form, change):
        set_beta_access(obj, obj.beta_access, by=request.user)

    def change_access(self, request, queryset, granted):
        changed = sum(set_beta_access(profile, granted, by=request.user) for profile in queryset)
        self.message_user(request, f"Beta access {'given to' if granted else 'taken away from'} {changed} {'person' if changed == 1 else 'people'}.")

    @admin.action(description="Give beta access", permissions=["change"])
    def give_access(self, request, queryset):
        self.change_access(request, queryset, True)

    @admin.action(description="Take beta access away", permissions=["change"])
    def take_access_away(self, request, queryset):
        self.change_access(request, queryset, False)

    @admin.action(description="Unlink Hackatime account", permissions=["change"])
    def unlink_hackatime_account(self, request, queryset):
        changed = sum(unlink_hackatime(profile, by=request.user) for profile in queryset)
        self.message_user(request, f"Hackatime unlinked from {changed} {'person' if changed == 1 else 'people'}.")


admin.site.unregister(User)
admin.site.register(User, UserAdmin)


class SettingsAdmin(ConstanceAdmin):
    """The settings page (Constance), with a warning for every switch that is on while its environment values are missing."""

    def changelist_view(self, request, extra_context=None):
        for sentence in switches.problems(live()):
            messages.warning(request, sentence)
        return super().changelist_view(request, extra_context)


admin.site.unregister([Config])
admin.site.register([Config], SettingsAdmin)
