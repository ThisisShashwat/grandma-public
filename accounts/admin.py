from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from accounts.models import Profile
from accounts.services import set_beta_access

User = get_user_model()


class ProfileInline(admin.StackedInline):
    model = Profile
    can_delete = False
    max_num = 1
    readonly_fields = ("hackatime_connected", "beta_access")        # beta access is given under Profiles, where every change is recorded


class UserAdmin(BaseUserAdmin):
    """Django's user admin plus the Profile. Accounts are made here for now (no signup page): username and password
    only, the person fills in the rest at /welcome/."""
    inlines = [ProfileInline]

    def get_inline_instances(self, request, obj=None):
        return super().get_inline_instances(request, obj) if obj else []        # nothing to show on the add page


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    """Who is let in while BETA_MODE is on. The only thing edited here is beta access, by hand or with the two actions, and every change is
    recorded in the audit log (accounts.services.set_beta_access). Profiles are made by the site, never here, and not deleted here."""
    list_display = ("user", "display_name", "beta_access", "staff")
    list_filter = ("beta_access", "user__is_staff")
    search_fields = ("user__username", "display_name")
    list_select_related = ("user",)
    ordering = ("user__username",)
    actions = ["give_access", "take_access_away"]
    fields = ("user", "display_name", "slack_id", "region", "timezone", "expertise", "onboarded_at", "tutorial_done_at", "beta_access")
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


admin.site.unregister(User)
admin.site.register(User, UserAdmin)
