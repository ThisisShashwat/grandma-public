"""The owner's control panel for the shop. Dollar values, markups and rates are visible here and nowhere else.

Only staff who were given shop permissions see these pages (Django's own model permissions); a staff account without them
gets a 403. A dedicated "can view costs" permission would be the next step (docs/security.md).
"""
from django.contrib import admin

from .models import RateClass, Region, RegionalPrice, ShopItem


class RegionalPriceInline(admin.TabularInline):
    model = RegionalPrice
    extra = 0
    fields = ("region", "usd_value", "enabled", "cookies_override", "cookies")
    readonly_fields = ("cookies",)


@admin.register(ShopItem)
class ShopItemAdmin(admin.ModelAdmin):
    list_display = ("name", "kind", "category", "stackable", "rate_class", "price", "rate", "active")
    list_filter = ("kind", "category", "stackable", "rate_class", "active")
    search_fields = ("name", "slug", "tagline")
    prepopulated_fields = {"slug": ("name",)}
    list_select_related = ("rate_class",)
    inlines = [RegionalPriceInline]
    actions = ["recompute_prices"]
    readonly_fields = ("cookies", "effective_rate", "upgrade_check")
    fieldsets = (
        ("The item", {"fields": ("name", "slug", "tagline", "description", "art", "kind", "category", "active", "sort_order")}),
        ("Who can buy how many", {"fields": ("stackable", "max_per_user", "stock", "base_item")}),
        ("Price (private: never shown to visitors)", {
            "fields": ("rate_class", "usd_value", "cookies", "cookies_override", "effective_rate", "upgrade_check")}),
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

    @admin.action(description="Recompute cookie prices (after changing a rate class or the pricing secret)", permissions=["change"])
    def recompute_prices(self, request, queryset):
        for item in queryset:
            item.save()
        self.message_user(request, f"Recomputed the prices of {len(queryset)} items and their regional prices.")


@admin.register(Region)
class RegionAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "sort_order", "active")
    list_editable = ("sort_order", "active")


@admin.register(RateClass)
class RateClassAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "markup", "cookies_per_dollar")
    prepopulated_fields = {"slug": ("name",)}

    @admin.display(description="cookies per dollar")
    def cookies_per_dollar(self, obj):
        return f"{obj.cookies_per_usd:.2f}"
