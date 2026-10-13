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

from accounts.public_id import PATTERN
from pages.live import live
from projects import services as project_services
from projects.models import Project
from submissions import ari, rules, services
from submissions.models import AriEvent

MAX_AGE, MAX_AHEAD = 300, 300         # seconds, both ways like Ari's own check (its source accepts 300 either side): a slow or fast clock of ours must never turn a true delivery into a final 4xx
TIMESTAMP = re.compile(r"[0-9]{1,12}")                  # unix seconds: plain digits only (int() would also take spaces, a sign and underscores)
DELIVERY_ID = re.compile(r"[\w.:-]{1,64}", re.ASCII)   # it ends up in a ledger key (max 100 characters), so it must be short and plain; the format is not in Ari's docs, so a little room
SHIP_ID = re.compile(r"[\w.:-]{1,40}", re.ASCII)        # Ari's id for a ship (AR-4821): Submission.ari_ship_id holds 40 characters
EXTERNAL_ID = re.compile(rf"grandma-({PATTERN})")       # what ari.external_id makes: the project's public id, nothing else is ours
MAX_MINUTES = 10**7                                     # far above any real answer: only keeps the arithmetic below from overflowing on a silly number (the real cap is rules.MAX_HOURS)
STATUS_OF = {"review.approved": rules.APPROVED, "review.changes": rules.CHANGES_REQUESTED, "review.rejected": rules.REJECTED}
TAKEN_BACK = ("review.reverted", "review.requeued")      # both leave needs_staff set: a delayed older approval must not pay on a decision Ari took back
FRAUD = "review.fraud"
SYSTEM = "system@ari"                                    # the reviewer email of Ari's own automatic decisions (docs/ari.txt: "the system reviewer"), compared in lower case
LOVED, RIBBON = "grandma_loved_it", "blue_ribbon"                        # the custom review fields the owner makes in Ari (docs/research/ari-webhooks.md)
UNMET = "Some of your notes are not met yet, dear: {names}. Fix them and hand it in again."
CHANGES = "I can't take it as it is, dear. Look it over once more and hand it in again."
CENTS = Decimal("0.01")


def receiving(enabled):
    """Does the address exist? `enabled` is the ARI_ENABLED switch (read strictly by the view). Not while it is off or the outbound secret is missing: a 404 for everybody."""
    return bool(enabled and settings.ARI_OUTBOUND_SECRET)


def trusted(raw, *, signature, timestamp, delivery_id, secret, now=None):
    """Whether this really is Ari's: a fresh timestamp, a plain delivery id, and X-Ari-Signature equal (constant time) to the hex HMAC-SHA256, with the outbound
    secret, of `timestamp + "." + delivery_id + "." + raw body` (docs/ari.txt, How delivery works)."""
    if not (secret and TIMESTAMP.fullmatch(timestamp) and DELIVERY_ID.fullmatch(delivery_id)):
        return False
    if not -MAX_AHEAD <= (now or time.time()) - int(timestamp) <= MAX_AGE:
        return False
    expected = ari.sign(f"{timestamp}.{delivery_id}.".encode() + raw, secret)
    return hmac.compare_digest(expected.encode(), signature.lower().encode())


def parse(raw):
    """The message as a dict with a string `event`, or None."""
    try:
        payload = json.loads(raw)
    except (ValueError, RecursionError):       # not JSON, or nested so deep that the parser gives up
        return None
    return payload if isinstance(payload, dict) and isinstance(payload.get("event"), str) else None


def text_of(payload, key):
    value = payload.get(key)
    return value if isinstance(value, str) else ""


def clean(text):
    """Text that is safe to store: no NUL characters and no lone surrogates (JSON can carry both; Postgres refuses a NUL and cannot encode a surrogate, which would make
    the same delivery a 500 forever)."""
    return text.replace("\x00", "").encode("utf-8", "ignore").decode("utf-8")


def find_submission(external_id, ari_id):
    """The submission an event is about: the one of this project that already has this Ari id (so a late message about an older round never touches a newer one), else
    the project's LATEST one when it has no Ari id yet (it adopts this one: the id of the 202 is not guaranteed). None for anything that is not ours, has no ship id, or is a
    ship we do not know."""
    match = EXTERNAL_ID.fullmatch(external_id)
    project = Project.objects.filter(public_id=match[1]).first() if match and SHIP_ID.fullmatch(ari_id) else None
    if project is None:
        return None
    known = project.submissions.filter(ari_ship_id=ari_id).first()
    latest = project.submissions.order_by("-round", "-id").first()
    if known is None and latest and not latest.ari_ship_id:
        latest.ari_ship_id = ari_id
        latest.save(update_fields=["ari_ship_id"])
        return latest
    return known


def hours_of(review):
    """approved_minutes / 60 to 2 places (never Ari's rounded approved_hours), or None when the minutes are missing, not a number, not above zero or absurdly big (the
    limit of rules.ari_hours_problem decides the rest)."""
    minutes = review.get("approved_minutes")
    if isinstance(minutes, bool) or not isinstance(minutes, (int, float)) or not 0 < minutes <= MAX_MINUTES:        # NaN and infinity fail the comparison too
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
    """review.approved, review.changes, review.rejected. A rejection by Ari's own system reviewer (an unreachable repo or demo, a timeout: its note tells the maker to fix
    the link and hand in again) is changes requested, with Ari's note and under the MAX_ROUNDS cap like staff; with no note or no round left nothing is applied and
    staff are told (services.apply_ari_decision refuses it). A human reviewer's rejection stays final."""
    event, status = payload["event"], STATUS_OF[payload["event"]]
    review = payload.get("review") if isinstance(payload.get("review"), dict) else {}
    reviewer = review.get("reviewer") if isinstance(review.get("reviewer"), dict) else {}
    answers, kept, note = answers_of(review), project_services.kept_demands(submission.project), clean(text_of(review, "note_to_maker"))
    checks = checks_of(answers, kept)
    system = status == rules.REJECTED and text_of(reviewer, "email").lower() == SYSTEM
    if system:
        status = rules.CHANGES_REQUESTED
    approved = status == rules.APPROVED
    return services.apply_ari_decision(
        submission.pk, event=event, delivery=delivery_id, status=status, approved_hours=hours_of(review) if approved else None,
        quality=approved and answers.get(LOVED) is True, ribbon=approved and answers.get(RIBBON) is True,
        public_note=changes_note(note, checks, kept) if status == rules.CHANGES_REQUESTED and not system else note, internal_note=clean(text_of(review, "audit_note")),
        reviewer_label=clean(text_of(reviewer, "email")) or clean(text_of(reviewer, "slack_id")), demand_checks=checks, max_rounds=live().MAX_ROUNDS if system else rules.NO_ROUND_CAP)


def fraud(submission, payload, delivery_id):
    """review.fraud (only with Ari's relay mode): it changes nothing about the ship, so only a verdict that is not a plain pass is told to staff."""
    check = payload.get("fraud") if isinstance(payload.get("fraud"), dict) else {}
    if check.get("verdict") == "passed":
        return rules.IGNORED
    services.flag_staff(submission, payload["event"], delivery_id, "fraud check")
    return rules.NEEDS_STAFF


def outcome_of(payload, delivery_id):
    """What this site does with one message. Events we do not act on (ship.updated: the maker's own words stay as they handed them in; anything new) are only recorded."""
    event = payload["event"]
    if event not in STATUS_OF and event not in TAKEN_BACK and event != FRAUD:
        return rules.IGNORED
    submission = find_submission(text_of(payload, "external_id"), text_of(payload, "id"))
    if submission is None:
        return rules.IGNORED
    if event in TAKEN_BACK:
        return services.revert_ari_decision(submission.pk, event=event, delivery=delivery_id)
    if event == FRAUD:
        return fraud(submission, payload, delivery_id)
    return decide(submission, payload, delivery_id)


def receive(payload, delivery_id):
    """Handle one verified message in one transaction with its AriEvent row, whose delivery id is unique: a repeat of a delivery is a no-op, and a fault of ours rolls
    the row back too, so Ari's retry is handled afresh. Returns the outcome."""
    with transaction.atomic():
        row, created = AriEvent.objects.get_or_create(delivery_id=delivery_id, defaults={"event": clean(payload["event"])[:40], "external_id": clean(text_of(payload, "external_id"))[:100]})
        if not created:
            return rules.NOOP
        row.outcome = outcome_of(payload, delivery_id)
        row.save(update_fields=["outcome"])
    return row.outcome
