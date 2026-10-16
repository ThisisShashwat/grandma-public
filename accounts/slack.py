"""The only place that talks to Slack: one direct message from the program's bot to a person, and an invite to channels. DISABLED in practice: nothing calls it
until the owner sets SLACK_BOT_TOKEN in the environment and switches SLACK_NOTIFICATIONS (submissions/notices.py) or fills SLACK_CHANNEL_IDS (accounts/onboarding.py)
in the admin.

`send_dm` and `invite` are BLOCKING (a 5 second timeout per call) and touch no database. A request never calls them directly: it hands one to `in_background`, which
runs it in a short lived daemon thread (all database reads and checks are done by the caller, before). Under test SLACK_SYNC makes `in_background` run it at once.
A failed call writes one warning with Slack's error code and nothing else: no Slack ID, no name, no text, never the token.

Slack API facts, checked 2026-10-04 against https://docs.slack.dev/reference/methods/chat.postMessage and 2026-10-16 against .../conversations.invite:
  - POST https://slack.com/api/<method>, JSON body, `Authorization: Bearer <token>`, Content-Type application/json.
  - chat.postMessage: a bot token (xoxb-) with the scope `chat:write` is enough. A member ID passed as `channel` (U... or W...) posts to the person's
    App Home messages tab of the bot. This needs the Messages tab enabled in the Slack app; if it returns `messages_tab_disabled`,
    the send fails. This was not tried with a real token. The person must be in the workspace the app is installed in.
  - conversations.invite: body {"channel": "<channel id C...>", "users": "<one member id>"}, one channel per call. A bot needs `channels:manage` (or the granular
    `channels:write.invites`) for public channels and must itself be a MEMBER of the channel (we never join: the owner adds the app by hand). Not tried with a real token.
    `already_in_channel` is a success; `not_in_channel`, `channel_not_found`, `user_is_restricted`, `cant_invite`, `is_archived`, `missing_scope`, `ratelimited` and the
    rest are a failed invite: logged by code, not retried. Tier 3 (50 or more a minute): a few invites per person are far below it.
  - Slack answers HTTP 200 even when it refuses: the body is {"ok": true, ...} or {"ok": false, "error": "..."}. Only a real rate limit
    is HTTP 429 with a Retry-After header. chat.postMessage has a special limit (about 1 message a second per channel, plus a workspace
    limit): one message per review is far below it, so a refusal is simply a failed send, never retried.
Text is plain: & < > are escaped by the caller, the way Slack's formatting guide asks.
"""
import json
import logging
import re
import threading
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from django.conf import settings

from accounts.validators import SLACK_ID
from program.content import slack_channels

API = "https://slack.com/api/"
TIMEOUT_SECONDS = 5
ALREADY_IN = "already_in_channel"
CODE = re.compile(r"[a-z_]{1,40}")
log = logging.getLogger(__name__)


def is_member_id(value):
    """Whether this is shaped like a Slack member ID. The last guard before a send: a channel ID or name must never be posted to."""
    return bool(SLACK_ID.fullmatch(value or ""))


def invites_on(cfg):
    """Whether people are offered the Slack channels: the bot token is in the environment and the admin setting names at least one valid channel. `cfg` is pages.live.live()."""
    return bool(settings.SLACK_BOT_TOKEN and slack_channels.ids(cfg.SLACK_CHANNEL_IDS))


def call(method, payload):
    """One Slack Web API call. "" when Slack accepted it, otherwise a short reason: Slack's own error code, `http_<status>`, or the class name of what went wrong on the way.
    Never the text of an exception (a library may print the token), never raises. The token goes only in the header."""
    request = Request(API + method, data=json.dumps(payload).encode(), method="POST",
                      headers={"Authorization": f"Bearer {settings.SLACK_BOT_TOKEN}", "Content-Type": "application/json; charset=utf-8"})
    try:
        with urlopen(request, timeout=TIMEOUT_SECONDS) as response:
            status, body = response.status, json.load(response)
    except HTTPError as error:
        return f"http_{error.code}"
    except Exception as error:
        return type(error).__name__
    if status != 200:
        return f"http_{status}"
    if isinstance(body, dict) and body.get("ok") is True:
        return ""
    code = body.get("error") if isinstance(body, dict) else None
    return code if isinstance(code, str) and CODE.fullmatch(code) else "not_ok"


def send_dm(slack_id, text):
    """Send `text` to this member as a direct message from the bot. True if Slack accepted it. Never raises: a missing token, a bad ID,
    a network error or a refusal from Slack is False (a review must never fail because of Slack). Blocking: call it through `in_background`."""
    if not settings.SLACK_BOT_TOKEN or not is_member_id(slack_id):
        return False
    error = call("chat.postMessage", {"channel": slack_id, "text": text})
    if error:
        log.warning("slack chat.postMessage failed: %s", error)
    return not error


def invite(slack_id, channel_ids):
    """Invite this member to each channel, one call per channel. Returns nothing and never raises; a channel that fails is logged by Slack's error code and the next
    one is still tried (`already_in_channel` is not a failure). Blocking: call it through `in_background`."""
    if not settings.SLACK_BOT_TOKEN or not is_member_id(slack_id):
        return
    for channel in channel_ids:
        error = call("conversations.invite", {"channel": channel, "users": slack_id})
        if error and error != ALREADY_IN:
            log.warning("slack conversations.invite failed: %s", error)


def in_background(function, *args):
    """Run a Slack call (`send_dm`, `invite`) without making the request wait for it: in a daemon thread that dies with the process, which does no database work.
    With SLACK_SYNC (the tests) it runs right here instead."""
    if settings.SLACK_SYNC:
        function(*args)
    else:
        threading.Thread(target=function, args=args, daemon=True).start()
