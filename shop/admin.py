"""The owner's control panel for the shop. Rate classes (markups) are visible here and nowhere else.

Only staff who were given shop permissions see these pages (Django's own model permissions); a staff account without them
gets a 403. A dedicated "can view costs" permission would be the next step (docs/security.md).
"""
from django.contrib import admin

from .models import RateClass, ShopItem


@admin.register(ShopItem)
class ShopItemAdmin(admin.ModelAdmin):
    list_display = ("name", "kind", "category", "stackable", "usd_value", "rate_class", "price", "rate", "active", "ribbon_only")
    list_filter = ("kind", "category", "stackable", "rate_class", "active", "ribbon_only")
    search_fields = ("name", "slug", "tagline")
    prepopulated_fields = {"slug": ("name",)}
    list_select_related = ("rate_class",)
    actions = ["recompute_prices"]
    readonly_fields = ("cookies", "effective_rate", "upgrade_check")
    fieldsets = (
        ("The item", {"fields": ("name", "slug", "tagline", "description", "art", "kind", "category", "active", "ribbon_only", "sort_order")}),
        ("Who can buy how many", {"fields": ("stackable", "max_per_user", "stock", "base_item")}),
        ("Price", {"fields": ("usd_value", "rate_class", "cookies", "cookies_override", "effective_rate", "upgrade_check")}),
    )

    @admin.display(description="cookies")
    def price(self, obj):
        return obj.effective_cookies

    @admin.display(description="cookies per dollar")
    def rate(self, obj):
        return f"{obj.cookies_per_dollar():.2f}"

    @admin.display(description="effective cookies per dollar")
    def effective_rate(self, obj):
        return self.rate(obj) if obj.pk else "-"

    @admin.display(description="upgrade rules")
    def upgrade_check(self, obj):
        return (obj.upgrade_problem() or "fine") if obj.pk else "-"

    @admin.action(description="Recompute cookie prices (after changing a rate class)", permissions=["change"])
    def recompute_prices(self, request, queryset):
        for item in queryset:
            item.save()
        self.message_user(request, f"Recomputed the prices of {len(queryset)} items.")


@admin.register(RateClass)
class RateClassAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "markup", "cookies_per_dollar")
    prepopulated_fields = {"slug": ("name",)}

    @admin.display(description="cookies per dollar")
    def cookies_per_dollar(self, obj):
        return f"{obj.cookies_per_usd:.2f}"
