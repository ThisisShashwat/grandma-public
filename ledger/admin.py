from uuid import uuid4

from django import forms
from django.contrib import admin
from django.core.exceptions import ValidationError

from ledger import rules, services
from ledger.models import CookieEntry


class AdjustmentForm(forms.ModelForm):
    """What staff fill in to correct a balance: who, how many cookies (negative to take), and why."""

    class Meta:
        model = CookieEntry
        fields = ("user", "amount", "reason")

    def clean(self):
        data = super().clean()
        user, amount = data.get("user"), data.get("amount")
        if user and amount is not None:
            if amount == 0:
                raise ValidationError("An adjustment of nothing is not an adjustment.")
            if rules.overdraws(services.balance(user), amount):
                raise ValidationError(f"That would take {user} below zero cookies (they have {services.balance(user)}).")
        return data


@admin.register(CookieEntry)
class CookieEntryAdmin(admin.ModelAdmin):
    """A history you can read and add to, never change: no change, no delete, and the only entry staff can add is an
    adjustment with a reason (the site writes every other kind, through ledger/services.py)."""

    form = AdjustmentForm
    list_display = ("created_at", "user", "amount", "kind", "reason", "created_by")
    list_filter = ("kind",)
    search_fields = ("user__username", "reason", "key")
    date_hierarchy = "created_at"
    autocomplete_fields = ("user",)

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def get_fields(self, request, obj=None):
        return ("user", "amount", "reason") if obj is None else ("user", "amount", "kind", "reason", "created_by", "created_at", "key")

    def save_model(self, request, obj, form, change):
        obj.kind, obj.created_by, obj.key = rules.ADJUSTMENT, request.user, f"admin-{uuid4().hex}"
        services.post(obj)
