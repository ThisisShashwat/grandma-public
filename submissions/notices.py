"""What a person is told outside the site when a decision on their project is saved: the Slack direct message for changes requested, approved and rejected. Written
DISABLED: nothing is sent until SLACK_NOTIFICATIONS is switched on in the admin AND SLACK_BOT_TOKEN is set in the environment. The message holds the dashboard link
and nothing else: never the reviewer's note (Grandma reads that to the person on the site), never the internal note, and a rejection is not called one (the site tells
it gently, through Grandma). The people are minors: nothing here logs a name, a Slack ID or a message. The checks are made here, in the request; only the HTTP call
runs in a background thread (accounts/slack.py in_background).
Known gap: a reviewer flip-flop (changes requested, then handed in, then changes requested again) sends a second message."""
from django.conf import settings
from django.urls import reverse

from accounts import slack
from accounts.models import Profile
from pages.live import live
from submissions import rules
from submissions.models import Submission

MESSAGES = {      # DRAFT copy for the owner to read (docs/grandma-scripts-to-read.md). Each ends with the dashboard link.
    rules.CHANGES_REQUESTED: "Grandma has read one of your projects. She wants some changes: come and hear them. {link}",
    rules.APPROVED: "Grandma has read your project and she liked it. Come and collect your cookies: {link}",
    rules.REJECTED: "Grandma has read your project. Come and hear what she thought: {link}",
}


def text_for(status):
    """The message for a decision."""
    return MESSAGES[status].format(link=settings.SITE_URL.rstrip("/") + reverse("dashboard"))


def switched_on():
    """The admin setting is on and the bot token is in the environment."""
    return bool(live().SLACK_NOTIFICATIONS and settings.SLACK_BOT_TOKEN)


def slack_id_of(user):
    """The Slack member ID on the person's Profile when linked with Hack Club Auth, "" otherwise."""
    profile = Profile.objects.filter(user=user).first()
    if not profile or not profile.hca_sub:
        return ""
    return profile.slack_id or ""


def tell(submission_id, status):
    """Tell the person the decision `status` was saved, if it is switched on and they have a Slack ID. True when the message was handed over (Slack answers later, in the
    background). Never raises: it runs after the review is committed (services.review) and a failure here must not touch the review."""
    try:
        if status not in MESSAGES or not switched_on():
            return False
        submission = Submission.objects.select_related("project__user").get(pk=submission_id)
        if submission.status != status or submission.claimed_at is not None or not submission.project.user.is_active:
            return False
        slack_id = slack_id_of(submission.project.user)
        if not slack.is_member_id(slack_id):
            return False
        slack.in_background(slack.send_dm, slack_id, text_for(status))
        return True
    except Exception:
        return False
