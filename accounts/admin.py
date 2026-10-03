from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from accounts.models import Profile

User = get_user_model()


class ProfileInline(admin.StackedInline):
    model = Profile
    can_delete = False
    max_num = 1
    readonly_fields = ("hackatime_connected",)


class UserAdmin(BaseUserAdmin):
    """Django's user admin plus the Profile. Accounts are made here for now (no signup page): username and password
    only, the person fills in the rest at /welcome/."""
    inlines = [ProfileInline]

    def get_inline_instances(self, request, obj=None):
        return super().get_inline_instances(request, obj) if obj else []        # nothing to show on the add page


admin.site.unregister(User)
admin.site.register(User, UserAdmin)
