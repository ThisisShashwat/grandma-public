"""Ari coming IN: what a reviewer decided, sent to POST /ari/result/ (submissions/views.py ari_result). This file checks the message and maps its events onto
submissions/services.py, where every rule stays (apply_ari_decision, revert_ari_decision). The rules for the answers, because Ari retries what it cannot deliver:
a forged, stale or malformed request gets a 4xx (Ari never retries those, which is right) and writes NOTHING; a message that is genuine but that we cannot or will
not act on (an unknown event or ship, a decision we refuse) gets a 200 and is recorded, so Ari never retries it forever; a fault of ours is a 500, so Ari retries.
Written from docs/ari.txt; nothing here has run against the real Ari (docs/research/ari-webhooks.md "Unverified")."""
import hmac
import json
import re
import time
from decimal import ROUND_HALF_UP, Decimal

from django.conf import settings
from django.db import transaction

from projects import services as project_services
from projects.models import Project
from submissions import ari, rules, services
from submissions.models import AriEvent

MAX_AGE, MAX_AHEAD = 300, 60          # seconds: Ari says ignore anything older than 5 minutes; a minute of clock skew is allowed so a true delivery is never lost to a 4xx
DELIVERY_ID = re.compile(r"[A-Za-z0-9_-]{1,64}")        # it ends up in a ledger key (max 100 characters), so it must be short and plain
PREFIX = "grandma-"
STATUS_OF = {"review.approved": rules.APPROVED, "review.changes": rules.CHANGES_REQUESTED, "review.rejected": rules.REJECTED}
TAKEN_BACK = {"review.reverted": True, "review.requeued": False}        # event -> whether staff are flagged (a reverted ship may never come back to Ari's queue)
LOVED, RIBBON = "grandma_loved_it", "blue_ribbon"                        # the custom review fields the owner makes in Ari (docs/research/ari-webhooks.md)
UNMET = "Some of your notes are not met yet, dear: {names}. Fix them and hand it in again."
CHANGES = "I can't take it as it is, dear. Look it over once more and hand it in again."
CENTS = Decimal("0.01")


def receiving(cfg):
    """Does the address exist? Not while Ari is off or the outbound secret is missing: it is a 404 for everybody."""
    return bool(cfg.ARI_ENABLED and settings.ARI_OUTBOUND_SECRET)


def trusted(raw, *, signature, timestamp, delivery_id, secret, now=None):
    """Whether this really is Ari's: a fresh timestamp, a plain delivery id, and X-Ari-Signature equal (constant time) to the hex HMAC-SHA256, with the outbound
    secret, of `timestamp + "." + delivery_id + "." + raw body` (docs/ari.txt, How delivery works)."""
    try:
        age = (now or time.time()) - int(timestamp)
    except ValueError:
        return False
    if not -MAX_AHEAD <= age <= MAX_AGE or not DELIVERY_ID.fullmatch(delivery_id):
        return False
    expected = ari.sign(f"{timestamp}.{delivery_id}.".encode() + raw, secret)
    return hmac.compare_digest(expected.encode(), signature.lower().encode())


def parse(raw):
    """The message as a dict with a string `event`, or None."""
    try:
        payload = json.loads(raw)
    except ValueError:
        return None
    return payload if isinstance(payload, dict) and isinstance(payload.get("event"), str) else None


def text_of(payload, key):
    value = payload.get(key)
    return value if isinstance(value, str) else ""


def find_submission(external_id, ari_id):
    """The submission an event is about: the project's LATEST one when it has no Ari id yet (it adopts this one) or the same id, else the older one with this id. None
    for an id that is not ours or a ship of another version (that is ignored: a stale message must not touch a newer round)."""
    project = Project.objects.filter(public_id=external_id[len(PREFIX):]).first() if external_id.startswith(PREFIX) else None
    latest = project.submissions.order_by("-round", "-id").first() if project else None
    if latest is None:
        return None
    if latest.ari_ship_id in ("", ari_id):
        if ari_id and not latest.ari_ship_id:
            latest.ari_ship_id = ari_id
            latest.save(update_fields=["ari_ship_id"])
        return latest
    return project.submissions.filter(ari_ship_id=ari_id).first() if ari_id else None


def hours_of(review):
    """approved_minutes / 60 to 2 places (never Ari's rounded approved_hours), or None when the minutes are missing or not a finite number."""
    minutes = review.get("approved_minutes")
    if isinstance(minutes, bool) or not isinstance(minutes, (int, float)) or not Decimal(str(minutes)).is_finite():
        return None
    return (Decimal(str(minutes)) / 60).quantize(CENTS, ROUND_HALF_UP)


def answers_of(review):
    """The custom review fields as {key: value}."""
    fields = review.get("fields")
    return {f["key"]: f.get("value") for f in fields if isinstance(f, dict) and isinstance(f.get("key"), str)} if isinstance(fields, list) else {}


def checks_of(answers, kept):
    """What the reviewer ticked per demand: demand_1_met is the first kept demand, and so on (a box beyond the demands kept is ignored)."""
    return [{"demand": demand.id, "met": answers[f"demand_{number}_met"] is True} for number, demand in enumerate(kept, start=1) if f"demand_{number}_met" in answers]


def changes_note(note, checks, kept):
    """What Grandma tells the maker: the reviewer's note, else the notes not met, else a plain sentence."""
    if note.strip():
        return note
    names = [demand.name for demand in kept if any(check["demand"] == demand.id and not check["met"] for check in checks)]
    return UNMET.format(names=", ".join(names)) if names else CHANGES


def decide(submission, payload, delivery_id):
    """review.approved, review.changes, review.rejected."""
    event, status = payload["event"], STATUS_OF[payload["event"]]
    review = payload.get("review") if isinstance(payload.get("review"), dict) else {}
    reviewer = review.get("reviewer") if isinstance(review.get("reviewer"), dict) else {}
    answers, kept, note = answers_of(review), project_services.kept_demands(submission.project), text_of(review, "note_to_maker")
    checks = checks_of(answers, kept)
    approved = status == rules.APPROVED
    return services.apply_ari_decision(
        submission.pk, event=event, delivery=delivery_id, status=status, approved_hours=hours_of(review) if approved else None,
        quality=approved and answers.get(LOVED) is True, ribbon=approved and answers.get(RIBBON) is True,
        public_note=changes_note(note, checks, kept) if status == rules.CHANGES_REQUESTED else note, internal_note=text_of(review, "audit_note"),
        reviewer_label=(text_of(reviewer, "email") or text_of(reviewer, "slack_id")), demand_checks=checks)


def outcome_of(payload, delivery_id):
    """What this site does with one message. Events we do not act on (ship.updated, review.fraud, anything new) are only recorded."""
    event = payload["event"]
    if event not in STATUS_OF and event not in TAKEN_BACK:
        return rules.IGNORED
    submission = find_submission(text_of(payload, "external_id"), text_of(payload, "id"))
    if submission is None:
        return rules.IGNORED
    if event in TAKEN_BACK:
        return services.revert_ari_decision(submission.pk, event=event, delivery=delivery_id, needs_staff=TAKEN_BACK[event])
    return decide(submission, payload, delivery_id)


def receive(payload, delivery_id):
    """Handle one verified message in one transaction with its AriEvent row, whose delivery id is unique: a repeat of a delivery is a no-op, and a fault of ours rolls
    the row back too, so Ari's retry is handled afresh. Returns the outcome."""
    with transaction.atomic():
        row, created = AriEvent.objects.get_or_create(delivery_id=delivery_id, defaults={"event": payload["event"][:40], "external_id": text_of(payload, "external_id")[:100]})
        if not created:
            return rules.NOOP
        row.outcome = outcome_of(payload, delivery_id)
        row.save(update_fields=["outcome"])
    return row.outcome
