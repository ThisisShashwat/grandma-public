import json

from django.contrib import admin
from django.utils.html import format_html

from audit.models import AuditEntry


@admin.register(AuditEntry)
class AuditEntryAdmin(admin.ModelAdmin):
    list_display = ("created_at", "action", "actor", "subject", "target_type", "target_id", "request_id")
    list_filter = ("action", "created_at")
    search_fields = ("action", "actor__username", "subject__username", "target_id", "request_id")
    list_select_related = ("actor", "subject")
    fields = ("created_at", "action", "actor", "subject", "target_type", "target_id", "request_id", "pretty_details")
    readonly_fields = ("created_at", "action", "actor", "subject", "target_type", "target_id", "request_id", "pretty_details", "details")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    @admin.display(description="Details")
    def pretty_details(self, obj):
        if obj is None:
            return ""
        return format_html("<pre>{}</pre>", json.dumps(obj.details, indent=2, sort_keys=True))

    details = pretty_details
