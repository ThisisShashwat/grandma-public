from django.conf import settings
from django.db import models
from django.db.models import Q

from ledger.rules import ADJUSTMENT, GAINS, KINDS, SPENDING


class AppendOnly(Exception):
    """An entry in the ledger is never changed or removed. To undo one, add another that cancels it."""


class EntryQuerySet(models.QuerySet):
    def update(self, **kwargs):
        raise AppendOnly("The cookie ledger is append only.")

    def delete(self):
        raise AppendOnly("The cookie ledger is append only.")

    def bulk_update(self, *args, **kwargs):
        raise AppendOnly("The cookie ledger is append only.")


class CookieEntry(models.Model):
    """One line of a person's cookie history. Their balance is the sum of their lines, nothing else is stored.
    Append only: the model refuses to be updated or deleted, and so does every queryset (rules in ledger/rules.py)."""

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="cookie_entries")
    amount = models.IntegerField(help_text="Whole cookies, positive to give, negative to take.")
    kind = models.CharField(max_length=10, choices=KINDS)
    reason = models.CharField(max_length=200)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name="+",
                                   help_text="The staff member who made a manual entry. Empty for entries the site made.")
    key = models.CharField("idempotency key", max_length=100, help_text="Posting the same key for the same person twice writes one entry.")

    objects = EntryQuerySet.as_manager()

    class Meta:
        ordering = ["-created_at", "-id"]
        verbose_name_plural = "cookie entries"
        constraints = [
            models.UniqueConstraint(fields=["user", "key"], name="cookie_entry_key_unique_per_user"),
            models.CheckConstraint(
                condition=Q(kind__in=GAINS, amount__gt=0) | Q(kind=SPENDING, amount__lt=0) | (Q(kind=ADJUSTMENT) & ~Q(amount=0)),
                name="cookie_entry_sign_fits_kind"),
            models.CheckConstraint(condition=~Q(reason="") & ~Q(key=""), name="cookie_entry_has_reason_and_key"),
        ]

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise AppendOnly("The cookie ledger is append only.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise AppendOnly("The cookie ledger is append only.")

    def __str__(self):
        return f"{self.user} {self.amount:+d} ({self.kind})"
