"""What a person is told outside the site when a review is saved. For now one thing: the Slack direct message when a reviewer asks
for changes. Written DISABLED: nothing is sent until SLACK_NOTIFICATIONS is switched on in the admin AND SLACK_BOT_TOKEN is set in the
environment. The message holds the dashboard link and nothing else: never the reviewer's note (Grandma reads
that to the person on the site), never the internal note. The people are minors: nothing here logs a name, a Slack ID or a message.
Known gap: a reviewer flip-flop (changes requested, then handed in, then changes requested again) sends a second message."""
from django.conf import settings
from django.urls import reverse

from accounts import slack
from accounts.models import Profile
from pages.live import live
from submissions import rules
from submissions.models import Submission


def changes_text():
    """The message."""
    link = settings.SITE_URL.rstrip("/") + reverse("dashboard")
    return f"Grandma has read one of your projects. She wants some changes: come and hear them. {link}"


def switched_on():
    """The admin setting is on and the bot token is in the environment."""
    return bool(live().SLACK_NOTIFICATIONS and settings.SLACK_BOT_TOKEN)


def slack_id_of(user):
    """The Slack member ID on the person's Profile when linked with Hack Club Auth, "" otherwise."""
    profile = Profile.objects.filter(user=user).first()
    if not profile or not profile.hca_sub:
        return ""
    return profile.slack_id or ""


def tell_changes_requested(submission_id):
    """Send the person the changes-requested message, if it is switched on and they have a Slack ID. True when Slack accepted it.
    Never raises: it runs after the review is committed (services.review) and a failure here must not touch the review."""
    try:
        if not switched_on():
            return False
        submission = Submission.objects.select_related("project__user").get(pk=submission_id)
        if (
            submission.status != rules.CHANGES_REQUESTED
            or submission.claimed_at is not None
            or not submission.project.user.is_active
        ):
            return False
        slack_id = slack_id_of(submission.project.user)
        return slack.is_member_id(slack_id) and slack.send_dm(slack_id, changes_text())
    except Exception:
        return False
