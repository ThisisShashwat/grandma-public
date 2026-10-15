"""The owner's control panel for the shop. Rate classes (markups) are visible here and nowhere else.

Only staff who were given shop permissions see these pages (Django's own model permissions); a staff account without them
gets a 403. A dedicated "can view costs" permission would be the next step (docs/security.md).
"""
from django import forms
from django.contrib import admin
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import UploadedFile

from . import art
from .models import RateClass, ShopItem, validate_art


class ShopItemForm(forms.ModelForm):
    class Meta:
        model = ShopItem
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["art"].help_text = "Only used when no picture is uploaded above. The name of a file that already ships in static/assets, for example grandma-cookie-jar.png. Not the name of your upload."

    def clean(self):
        """An uploaded picture wins, so the file name box must never block it: whatever was typed there (the upload's own name, a typo, nothing) is dropped and the stored name stays."""
        cleaned = super().clean()
        if cleaned.get("art_upload"):
            try:
                validate_art(cleaned.get("art", ""))         # the model's own check runs later: a good name is kept, anything else is replaced before it can fail
            except ValidationError:
                self._errors.pop("art", None)                # an empty box is "required" at the form's level
                cleaned["art"] = self.instance.art
        return cleaned

    def clean_art_upload(self):
        """A new picture is made safe and small (shop/art.py); an unchanged or cleared one passes through."""
        picture = self.cleaned_data["art_upload"]
        return art.clean(picture) if isinstance(picture, UploadedFile) else picture


@admin.register(ShopItem)
class ShopItemAdmin(admin.ModelAdmin):
    form = ShopItemForm
    list_display = ("name", "kind", "category", "stackable", "usd_value", "rate_class", "price", "rate", "active", "ribbon_only", "show_on_home")
    list_editable = ("show_on_home",)           # tick it from the list: the home page peek (shop/peek.py)
    list_filter = ("kind", "category", "stackable", "rate_class", "active", "ribbon_only", "show_on_home")
    search_fields = ("name", "slug", "tagline")
    prepopulated_fields = {"slug": ("name",)}
    list_select_related = ("rate_class",)
    actions = ["recompute_prices"]
    readonly_fields = ("cookies", "effective_rate", "upgrade_check")
    fieldsets = (
        ("The item", {"fields": ("name", "slug", "tagline", "description", "art_upload", "art", "kind", "category", "active", "ribbon_only", "show_on_home", "sort_order")}),
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
