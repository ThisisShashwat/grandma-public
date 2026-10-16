from audit.middleware import current
from audit.models import AuditEntry


def record(action, *, actor=None, subject=None, target=None, details=None):
    """Write one entry. Call it INSIDE the transaction of the thing it records, so the two commit or roll back together. `target` is a model instance (its label and pk are stored). `details` is a small JSON-able dict of ids, field names, statuses, counts and amounts: NEVER passwords, tokens, IP addresses or free text a person typed (names, ideas, notes, links, descriptions)."""
    if details is None:
        details = {}
    target_type = target._meta.label if target is not None else ""
    target_id = target.pk if target is not None else None
    return AuditEntry.objects.create(
        action=action,
        actor=actor,
        subject=subject,
        target_type=target_type,
        target_id=target_id,
        details=details,
        request_id=current.get(),
    )


def count_since(action, subject, since):
    """How many entries of this action are about this person since `since`: the count behind a rolling limit (no counter table). Read only."""
    return AuditEntry.objects.filter(action=action, subject=subject, created_at__gte=since).count()
