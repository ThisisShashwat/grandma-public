"""The staff side of the metrics: one read only page, Admin > Site metrics > Metrics (docs/metrics.md). It borrows the admin entry of the
ActiveDay table to get a place in the index and the permission `metrics.view_activeday` (superusers, or anybody given it). There is no list,
no form and no other address: a page of numbers, nothing to add, change or delete."""
from django.contrib import admin
from django.core.exceptions import PermissionDenied
from django.template.response import TemplateResponse
from django.urls import path

from metrics import queries
from metrics.models import ActiveDay


@admin.register(ActiveDay)
class MetricsAdmin(admin.ModelAdmin):
    def get_urls(self):
        return [path("", self.admin_site.admin_view(self.changelist_view), name="metrics_activeday_changelist")]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def changelist_view(self, request, extra_context=None):
        if not self.has_view_permission(request):
            raise PermissionDenied
        report = queries.build(queries.parse_days(request.GET.get("days")))
        context = {**self.admin_site.each_context(request), "title": "Metrics", "opts": self.opts, "report": report, "ranges": queries.RANGES}
        return TemplateResponse(request, "admin/metrics/report.html", context)
