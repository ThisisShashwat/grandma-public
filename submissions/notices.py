"""What a person is told outside the site when a review is saved. For now one thing: the Slack direct message when a reviewer asks
for changes. Written DISABLED: nothing is sent until SLACK_NOTIFICATIONS is switched on in the admin AND SLACK_BOT_TOKEN is set in the
environment. The message holds the project name and the dashboard link and nothing else: never the reviewer's note (Grandma reads
that to the person on the site), never the internal note. The people are minors: nothing here logs a name, a Slack ID or a message."""
from html import escape

from django.conf import settings
from django.urls import reverse

from accounts import slack
from accounts.models import Profile
from pages.live import live
from submissions.models import Submission


def changes_text(project_name):
    """The message. Slack's formatting characters in the name are escaped, so a project called <!channel> says exactly that."""
    link = settings.SITE_URL.rstrip("/") + reverse("dashboard")
    return f"Grandma has read {escape(project_name, quote=False)}. She wants some changes: come and hear them. {link}"


def switched_on():
    """The admin setting is on and the bot token is in the environment."""
    return bool(live().SLACK_NOTIFICATIONS and settings.SLACK_BOT_TOKEN)


def slack_id_of(user):
    """The Slack member ID on the person's Profile, "" when there is no Profile or no ID."""
    return Profile.objects.filter(user=user).values_list("slack_id", flat=True).first() or ""


def tell_changes_requested(submission_id):
    """Send the person the changes-requested message, if it is switched on and they have a Slack ID. True when Slack accepted it.
    Never raises: it runs after the review is committed (services.review) and a failure here must not touch the review."""
    try:
        if not switched_on():
            return False
        submission = Submission.objects.select_related("project__user").get(pk=submission_id)
        slack_id = slack_id_of(submission.project.user)
        return slack.is_member_id(slack_id) and slack.send_dm(slack_id, changes_text(submission.project.name))
    except Exception:
        return False
