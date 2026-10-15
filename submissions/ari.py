"""Ari, HQ's review tool, going OUT: every hand-in is sent as a signed ship, and the exact bytes are kept in an outbox row (AriDelivery) so a resend
is byte for byte the same and Ari answers 200 duplicate within the hour. What comes back is ari_inbound.py. Written DISABLED: nothing is sent
until ARI_ENABLED is on in the admin AND the three ARI_ values are in the environment. The secrets are never stored, logged, audited or returned;
last_error is always one of the fixed words below, never a response body. The people are minors: nothing here logs a name, an email or a link.
The fields are exactly docs/ari.txt; the mapping and the reasons are docs/research/ari-webhooks.md and docs/submissions.md "Ari"."""
import hashlib
import hmac
import json
from functools import partial

import requests
from django.conf import settings
from django.db import transaction
from django.urls import reverse
from django.utils import timezone

from pages.live import live
from projects import services as project_services
from submissions import rules
from submissions.models import AriDelivery

INGEST_URL = "https://webhooks.ari.hackclub.com/api/ingest"
TIMEOUT = 10
INGEST, WITHDRAW = "ingest", "withdraw"
PENDING, SENT, FAILED = "pending", "sent", "failed"
NO_EMAIL, REFUSED, UNREACHABLE, TIMED_OUT, SERVER_SIDE, ABANDONED = "no email", "refused by Ari", "network error", "timed out", "server error", "project abandoned"
RETRY_CODES = (408, 429)         # a 4xx that Ari wants retried (docs/ari.txt delivery rules, applied to what we send too): everything else 4xx is a no
EVIDENCE = ["commits", "elapsed", "devlog"]
UPDATE_MESSAGE = "Round {round}: the maker fixed what the last review asked for and handed it in again."
AI_NONE = "none declared"
META_KEY, META_VALUE = 80, 2000


def enabled(cfg):
    """Is sending to Ari on? `cfg` is pages.live.live()."""
    return bool(cfg.ARI_ENABLED and settings.ARI_PROGRAM_ID and settings.ARI_INGEST_SECRET and settings.ARI_OUTBOUND_SECRET)


def external_id(project):
    """Our id for the ship: the PROJECT, so a later round is a new version of the same ship and keeps its place in Ari's queue."""
    return f"grandma-{project.public_id}"


def site_address(path):
    return path if path.startswith("https://") else settings.SITE_URL.rstrip("/") + path      # a screenshot on R2 already has a full address


def email_of(submission):
    return submission.project.user.profile.email


def maker_of(submission):
    user = submission.project.user
    profile = user.profile
    maker = {"email": profile.email, "name": profile.display_name or user.get_username(), "slack_id": profile.slack_id}
    if profile.hackatime_user_id:
        maker["hackatime_id"] = profile.hackatime_user_id
    return maker


def meta_of(submission):
    """The flat strings the reviewer reads next to the ship: the demands (the reviewer ticks them in the custom review fields), the declarations, the public page."""
    project = submission.project
    kept = project_services.kept_demands(project)
    entries = {"Category": ", ".join(filter(None, (project.category.name, project.subcategory.name if project.subcategory else ""))), "Round": str(submission.round)}
    entries |= {f"Demand {number}": f"{demand.name} (tier {demand.tier}): {demand.rule}" for number, demand in enumerate(kept, start=1)}
    entries["AI declaration"] = submission.ai_declaration_text or AI_NONE
    entries["Ticked declarations"] = ", ".join(submission.declarations)
    entries["Public page"] = site_address(reverse("public_project_bare", kwargs={"public_id": project.public_id}))     # the page answers with a 301 to its canonical address
    if project.started_at:
        entries["Started after Grandma"] = project.started_at.isoformat()
    return {key[:META_KEY]: value[:META_VALUE] for key, value in entries.items()}


def build_ship(submission):
    """The ship, with exactly the fields of docs/ari.txt that we have (`hours` is ignored by Ari, `collaborators` is off for us)."""
    project = submission.project
    ship = {
        "external_id": external_id(project),
        "title": project.name,
        "description": submission.description,
        "maker": maker_of(submission),
        "repo_url": submission.repo_url,
        "demo_url": submission.playable_url or submission.recording_url,
        "thumbnail_url": site_address(submission.screenshot.url) if submission.screenshot else "",      # empty only after a staff takedown deleted the file
        "track": "software",
        "hackatime_projects": list(submission.hackatime_projects),
        "evidence": EVIDENCE,
        "meta": meta_of(submission),
    }
    if submission.round > 1:
        ship |= {"is_update": True, "update_message": UPDATE_MESSAGE.format(round=submission.round)}
    return ship


def encode(body):
    """The exact bytes that are signed and sent."""
    return json.dumps(body, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def sign(raw, secret):
    """The hex HMAC-SHA256 of the raw bytes: Ari's X-Ari-Signature (both ways; inbound signs more, see ari_inbound.py)."""
    return hmac.new(secret.encode(), raw, hashlib.sha256).hexdigest()


# the outbox

def queue_ingest(submission):
    """Write the ship's outbox row, inside the hand-in's transaction. Without an email Ari cannot find the maker: the row is made already failed ("no email"), for staff to see."""
    row = AriDelivery(submission=submission, kind=INGEST, body=encode(build_ship(submission)))
    if not email_of(submission):
        row.status, row.last_error = FAILED, NO_EMAIL
    row.save()
    return row


def queue_withdraw(submission):
    return AriDelivery.objects.create(submission=submission, kind=WITHDRAW, body=encode({"external_id": external_id(submission.project)}))


def queue_and_try(submission):
    """The hand-in's hook: queue the ship, and once the transaction has committed try it once (never before: a rollback must send nothing)."""
    row = queue_ingest(submission)
    transaction.on_commit(partial(try_once, row.pk))


def withdraw_if_open(sender, project, **kwargs):
    """Staff abandoned a project (projects.signals.project_abandoned). A ship not yet sent never goes; one Ari holds is withdrawn (Ari refuses it once decided: that is its answer, not ours)."""
    submission = project.submissions.order_by("-round", "-id").first()
    if submission is None or submission.status != rules.SUBMITTED:
        return
    submission.ari_deliveries.filter(kind=INGEST, status=PENDING).update(status=FAILED, last_error=ABANDONED)
    if enabled(live()) and submission.ari_deliveries.filter(kind=INGEST, status=SENT).exists():
        transaction.on_commit(partial(try_once, queue_withdraw(submission).pk))


# sending

def url_of(row):
    base = f"{INGEST_URL}/{settings.ARI_PROGRAM_ID}"
    return base if row.kind == INGEST else f"{base}/withdraw"


def ship_id_of(response):
    """Ari's id for the ship from a 202 or 200 body ({"id": "AR-4821", ...}), "" when the body is not that."""
    try:
        found = response.json().get("id")
    except (ValueError, AttributeError):
        return ""
    return found[:40] if isinstance(found, str) else ""


def record(row, response):
    """What Ari answered: 2xx is sent; a 4xx (except 408 and 429) is a no, so failed and never looped; anything else stays pending for the next pass."""
    code = response.status_code
    row.last_status = code
    if 200 <= code < 300:
        row.status, row.last_error, row.sent_at = SENT, "", timezone.now()
        if row.kind == INGEST and (found := ship_id_of(response)):
            row.submission.ari_ship_id = found
            row.submission.save(update_fields=["ari_ship_id"])
    elif 400 <= code < 500 and code not in RETRY_CODES:
        row.status, row.last_error = FAILED, REFUSED
    else:
        row.status, row.last_error = PENDING, SERVER_SIDE
    row.save()


def post(row):
    """One POST of the stored bytes with their signature. Redirects are not followed (the signature must never travel on). Returns the response or None."""
    raw = bytes(row.body)
    headers = {"Content-Type": "application/json", "X-Ari-Signature": sign(raw, settings.ARI_INGEST_SECRET)}
    try:
        return requests.post(url_of(row), data=raw, headers=headers, timeout=TIMEOUT, allow_redirects=False)
    except requests.Timeout:
        row.last_error = TIMED_OUT
    except requests.RequestException:
        row.last_error = UNREACHABLE


def deliver(row):
    """One try at one outbox row. Never raises a network problem: it is written on the row. A ship with no email is not sent (the person may sign in again and
    the next pass builds it again); everything else resends the stored bytes."""
    if row.kind == INGEST and row.last_error == NO_EMAIL:
        row.body = encode(build_ship(row.submission))
    if row.kind == INGEST and not email_of(row.submission):
        row.status, row.last_error = FAILED, NO_EMAIL
        row.save()
        return row
    row.attempts += 1
    response = post(row)
    if response is None:
        row.status = PENDING
        row.save()
    else:
        record(row, response)
    return row


def try_once(row_id):
    """After the hand-in committed: one try. Whatever goes wrong here never touches the hand-in (the row stays pending for the next pass)."""
    try:
        row = AriDelivery.objects.select_related("submission__project__user__profile").get(pk=row_id)
        if row.status == PENDING and enabled(live()):
            deliver(row)
    except Exception:
        return


def send_pending(*, retry_failed=False):
    """One pass over the outbox (the cron command): the pending rows, and the failed ones only on request. Returns how many it tried."""
    statuses = (PENDING, FAILED) if retry_failed else (PENDING,)
    rows = list(AriDelivery.objects.filter(status__in=statuses).select_related("submission__project__user__profile").order_by("id"))
    for row in rows:
        deliver(row)
    return len(rows)
