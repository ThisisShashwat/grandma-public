"""Complaints: what a person sends Grandma when she should demand something new (docs/projects.md "Complaints"). Private: staff read them
in the admin and nothing here hands one to anybody else. The limit is the pure rule in rules.py; this layer applies it."""
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from audit import services as audit
from projects import rules
from projects.models import Complaint
from projects.services import lock_person

TOO_MANY = "That's enough complaints for one day, dear. I only have the two hands. Come back tomorrow."


@transaction.atomic
def send_complaint(user, title, text, example=""):
    """Store one complaint and record it in the audit log, in one transaction, under the person's lock so two clicks cannot both fit under
    the limit. ValidationError, and nothing written, for a bad length or character or when they have already sent COMPLAINT_LIMIT in the
    last COMPLAINT_WINDOW. The audit entry holds the complaint's id and nothing they typed."""
    lock_person(user)
    complaint = Complaint(user=user, title=title.strip(), text=rules.tidy(text), example=example.strip())
    complaint.full_clean()
    sent = Complaint.objects.filter(user=user, created_at__gte=timezone.now() - rules.COMPLAINT_WINDOW).count()
    if sent >= rules.COMPLAINT_LIMIT:
        raise ValidationError(TOO_MANY)
    complaint.save()
    audit.record("complaint.send", actor=user, subject=user, target=complaint, details={"complaint": complaint.pk})
    return complaint
