"""The only place that talks to Slack: one direct message from the program's bot to a person. DISABLED in practice: nothing calls it
until the owner sets SLACK_BOT_TOKEN in the environment and switches SLACK_NOTIFICATIONS on in the admin (submissions/notices.py).

Slack API facts, checked 2026-10-04 against https://docs.slack.dev/reference/methods/chat.postMessage (and /apis/web-api/rate-limits):
  - POST https://slack.com/api/chat.postMessage, JSON body, `Authorization: Bearer <token>`, Content-Type application/json.
  - A bot token (xoxb-) with the scope `chat:write` is enough. A member ID passed as `channel` (U... or W...) posts to the person's
    App Home messages tab of the bot. This needs the Messages tab enabled in the Slack app; if it returns `messages_tab_disabled`,
    the send returns False. This was not tried with a real token. The person must be in the workspace the app is installed in.
  - Slack answers HTTP 200 even when it refuses: the body is {"ok": true, ...} or {"ok": false, "error": "..."}. Only a real rate limit
    is HTTP 429 with a Retry-After header. chat.postMessage has a special limit (about 1 message a second per channel, plus a workspace
    limit): one message per review is far below it, so a refusal is simply a failed send, never retried.
Text is plain: & < > are escaped by the caller, the way Slack's formatting guide asks.
"""
import json
from urllib.request import Request, urlopen

from django.conf import settings

from accounts.validators import SLACK_ID

POST_MESSAGE = "https://slack.com/api/chat.postMessage"
TIMEOUT_SECONDS = 5


def is_member_id(value):
    """Whether this is shaped like a Slack member ID. The last guard before a send: a channel ID or name must never be posted to."""
    return bool(SLACK_ID.fullmatch(value or ""))


def send_dm(slack_id, text):
    """Send `text` to this member as a direct message from the bot. True if Slack accepted it. Never raises: a missing token, a bad ID,
    a network error or a refusal from Slack is False (a review must never fail because of Slack). The token goes only in the header."""
    token = settings.SLACK_BOT_TOKEN
    if not token or not is_member_id(slack_id):
        return False
    request = Request(POST_MESSAGE, data=json.dumps({"channel": slack_id, "text": text}).encode(), method="POST",
                      headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json; charset=utf-8"})
    try:
        with urlopen(request, timeout=TIMEOUT_SECONDS) as response:
            return response.status == 200 and json.load(response).get("ok") is True
    except Exception:
        return False
