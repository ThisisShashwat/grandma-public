from django.conf import settings
from django.db import models


class AppendOnly(Exception):
    """An entry in the audit log is never changed or removed."""


class AuditQuerySet(models.QuerySet):
    def update(self, **kwargs):
        raise AppendOnly("The audit log is append only.")

    def delete(self):
        raise AppendOnly("The audit log is append only.")

    def bulk_update(self, *args, **kwargs):
        raise AppendOnly("The audit log is append only.")


class AuditEntry(models.Model):
    """An append-only record of a state-changing action."""

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name="+")
    subject = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name="+")
    action = models.CharField(max_length=40, db_index=True)
    target_type = models.CharField(max_length=60, blank=True)
    target_id = models.PositiveBigIntegerField(null=True, blank=True)
    details = models.JSONField(default=dict, blank=True)
    request_id = models.CharField(max_length=32, blank=True, db_index=True)

    objects = AuditQuerySet.as_manager()

    class Meta:
        ordering = ["-id"]
        verbose_name_plural = "audit entries"
        indexes = [
            models.Index(fields=["target_type", "target_id"], name="audit_entry_target_idx"),
            models.Index(fields=["subject", "created_at"], name="audit_entry_subject_time_idx"),
        ]

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise AppendOnly("The audit log is append only.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise AppendOnly("The audit log is append only.")

    def __str__(self):
        return f"{self.action} #{self.id}"
