"""The Slack channels a new person is offered, as the admin setting SLACK_CHANNEL_IDS writes them: channel IDs (C followed by capital letters and digits),
comma separated. Channel NAMES cannot be invited to, only IDs can (accounts/slack.py). Empty means the feature is off."""
import re

CHANNEL_ID = re.compile(r"C[A-Z0-9]{8,}")
MAX_CHANNELS = 5


def parse(text):
    """The channel IDs in a text, in the order written (spaces around the commas are fine, an empty text is no channels). ValueError with a sentence for a bad ID,
    a repeated one or more than MAX_CHANNELS."""
    ids = [part.strip() for part in text.split(",") if part.strip()]
    for channel in ids:
        if not CHANNEL_ID.fullmatch(channel):
            raise ValueError("Each channel ID is a C followed by capital letters and digits, like C01ABC23DEF. Find it at the bottom of the channel's About tab in Slack, "
                             "and separate several with commas. Channel names do not work.")
    if len(set(ids)) != len(ids):
        raise ValueError("A channel ID is listed twice.")
    if len(ids) > MAX_CHANNELS:
        raise ValueError(f"At most {MAX_CHANNELS} channels.")
    return tuple(ids)


def ids(text):
    """The channel IDs for the setting's text. A broken text gives none, never part of a list: the feature is off rather than inviting people to the wrong place."""
    try:
        return parse(text or "")
    except ValueError:
        return ()
