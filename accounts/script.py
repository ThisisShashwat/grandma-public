"""What Grandma says during onboarding. Text and steps only: the opening, the software-only rule, the questions, the Hackatime step and the two tutorial parts.
Who sees which part is decided in accounts/onboarding.py; how a step is built is talk/dialogue.py."""
from django.urls import reverse

from accounts.validators import suggested_timezones, validate_display_name, validate_polite_name, validate_slack_id, validate_timezone
from program.content.expertise import EXPERTISE
from program.content.regions import REGIONS
from talk.dialogue import AskChoice, AskText, End, Say

OPENING = [
    Say(face="wave", lines=(
        "Oh! Somebody's here. Come in, come in, and wipe your feet.",
        "I'm Grandma. I'll be bossing you about for a good while, so I need to write a few things down.")),
]

def region_guess_line(label):
    """The extra line when the time zone pointed at a region: a guess, never a fact (the braces are doubled because the lines are formatted)."""
    return f"That time zone makes me think {label.replace('{', '{{').replace('}', '}}')}. Tap it if I'm right, dear, or tap your own."


SOFTWARE_ONLY = Say(face="finger", lines=(
    "One rule before we start, dear: software only.",
    "Websites, apps, games, tools, bots, anything made of code. Nothing you have to plug in or solder."))

QUESTIONS = [
    AskText(key="display_name", face="writing", label="Your name", validators=(validate_display_name, validate_polite_name), max_length=30, button="That's me",
            attrs={"autocomplete": "nickname", "autocapitalize": "words", "spellcheck": "false"}, lines=(
                "First things first. What should I call you, dear?",
                "Pick a name you don't mind other people seeing. It goes on my wall.")),
    Say(face="smug", lines=("{display_name}.", "Hm. I've heard worse.")),
    AskText(key="slack_id", face="magnifier", label="Slack member ID, like U01ABC23DEF", validators=(validate_slack_id,), max_length=12,
            button="That's my ID", attrs={"autocomplete": "off", "autocapitalize": "characters", "spellcheck": "false"}, lines=(
                "Now your Slack ID, {display_name}. Not your username. Your ID.",
                "Open your profile in Slack, tap the three dots and pick Copy member ID. It starts with a U or a W.")),
    AskText(key="timezone", face="clipboard", label="Time zone, like Asia/Kolkata", validators=(validate_timezone,), max_length=64,
            prefill="timezone", suggestions=suggested_timezones, button="That's my zone", attrs={"autocomplete": "off", "autocapitalize": "off", "spellcheck": "false"}, lines=(
                "Your time zone next, so I don't phone you at silly o'clock.",
                "Your browser usually knows. I've asked it nicely.")),
    AskChoice(key="region", face="phone", choices=tuple(REGIONS), lines=(
        "And where in the world are you, {display_name}?", "I need to know how far I have to shout.")),
    AskChoice(key="expertise", face="eyeroll", choices=tuple(EXPERTISE), lines=(
        "How much of this have you done before?", "Be honest. I can tell.")),
]


# What connecting lets her do, before the button (only while the connection is on: the greyed-out stub connects nothing).
HACKATIME_PRIVACY = ("I only look at your project list and the hours of the projects you tick. I keep the key encrypted and show it to nobody. "
                     "Cut me off whenever you like, in Hackatime's Privacy and Security settings, and I'll just ask you to connect again.")


def hackatime_step(enabled=False, connected=False):
    """The Hackatime step (accounts/hackatime.py). Switched off (the default) it is a greyed-out button that lets people carry on, because nobody could
    finish onboarding otherwise. Switched on it is the real thing: the button goes to the connect page, there is no Go on, and the step is not played
    once they are connected (`connected`: the person's Profile), so the only way past it is to connect."""
    if not enabled:
        return Say(face="finger", disabled="Connect Hackatime", lines=(
            "Now the important bit.",
            "I count your hours with a thing called Hackatime. No Hackatime, no hours. No hours, no cookies.",
            "Press the button and we'll hook you up. ...Oh. It's not ready. Whoever built this place hasn't plugged it in yet. Carry on, dear, we'll come back to it."))
    return Say(face="finger", link=("Connect Hackatime", reverse("connect_hackatime")), locked=True, when=lambda answers: not connected, lines=(
        "Now the important bit.",
        "I count your hours with a thing called Hackatime. No Hackatime, no hours. No hours, no cookies.",
        HACKATIME_PRIVACY,
        "Press the button and Hackatime will ask if I may take a look."))


def hackatime_connected_step(enabled=False, connected=False):
    """What she says once Hackatime is connected: played right after the Hackatime step, only for somebody who is connected (the step before it is skipped then)."""
    return Say(face="approved", when=lambda answers: enabled and connected, lines=(
        "There, dear. Hackatime is hooked up.",
        "Now mind you keep it counting while you build. No hours, no cookies."))


SKIP_OFFER = AskChoice(
    key="tutorial", face="sideeye", choices=(("skip", "No thanks, I know my way around"), ("show", "Fine, lecture me")), lines=(
        "You've shipped before? Show-off.", "I have a few little words about how Hack Club works. Want them?"))

# The Hack Club basics (part 0): the only part experience may skip. Draft copy by Claude, 2026-10-07, for the owner to read.
PART_BASICS = [
    Say(face="finger", lines=(
        "One more thing, dear, and it's about Hack Club, not about me.",
        "Hack Club is a nonprofit of teenagers who make things. I only run one little corner of it.")),
    Say(face="magnifier", lines=(
        "To ship something means to finish it and put it where other people can use it. A real link, not a promise.",
        "A half built thing in a folder on your laptop has not shipped, dear. I don't count those.")),
    Say(face="note", lines=(
        "This is what Hack Club calls a YSWS. You Ship, We Ship.",
        "You ship a project, and they ship you something back. Here, what comes back is cookies, and cookies turn into grants.")),
    Say(face="hug", lines=(
        "A grant is money on a card from Hack Club's bank, for one particular thing. You buy the thing yourself, and you show what you bought.",
        "That's all it is. No magic, no parcels.")),
]

PART_ONE = [
    Say(face="finger", lines=("Lesson one, dear. How this works.", "It is very simple. I am bossy and you are talented.")),
    Say(face="note", lines=(
        "You tell me what you want to build. Anything you like. I never choose what.",
        "Then I reach into my cookie jar and pull out notes. Each note is a demand: a silly rule about how you build it.")),
    Say(face="sideeye", lines=(
        "I deal you a handful of notes and you keep one, two or three. Never zero.",
        "Don't like the hand? Ask me to deal again. The first few times are free. After that it costs cookies, because I am not a charity.")),
    Say(face="clipboard", lines=(
        "Then you build it, dear, all on your own, and nobody is timing you. Half an hour or ten days, it takes what it takes. Hackatime counts your hours while you type.",
        "Start before you've talked to me and I will know. I always know.")),
    Say(face="magnifier", lines=(
        "When it's done you hand it in to me. A reviewer checks your work and your hours, and I give my verdict.",
        "Now. Cookies.")),
]

PART_TWO = [
    Say(face="cookie-jar", lines=(
        "Lesson two. Cookies.",
        "Cookies are what you earn for the hours you ship. Spicier demands and a project I love make every hour worth more.")),
    Say(face="smug", lines=(
        "They don't just appear, mind. Once a reviewer has looked at your project, you come and see me and I hand them over myself.",
        "With a lecture.")),
    Say(face="hug", lines=(
        "You spend them in my Pantry. It sells grants, not parcels.",
        "A grant is money for one particular thing. You buy the thing yourself and I trust you. Mostly.")),
    Say(face="wag", lines=(
        "Some grants stack, some don't. Some can be topped up with upgrade grants to make them bigger.",
        "Every item on the shelf tells you what it costs and what it's worth. Read it before you spend, dear.")),
]

TUTORIAL_CLOSE = [
    Say(face="approved", lines=(
        "And that's everything. Questions go in the Slack.", "Somebody there is much less grumpy than me.")),
]

ENDING = End(face="overjoyed", button="To my dashboard", lines=(
    "{display_name}, you're all set.", "Off you go. And wipe your feet on the way out."))

# What Grandma says when a Hack Club sign-in does not go through (accounts/views.py): one fixed label and sentence per case, so nothing from Hack Club
# or the request is ever repeated. A refusal for an inactive user, a clash of ids or an invalid identity gets "no_account".
HCA_REFUSALS = {
    "not_eligible": ("Not yet, dear", "Hack Club hasn't marked you as ready for a program like mine. Come back when Hack Club has checked you, and I'll be here."),
    "no_slack_id": ("No Slack ID", "Hack Club didn't tell me your Slack ID, dear, and I need it to reach you. Join the Hack Club Slack, then try again."),
    "no_account": ("I can't take you on", "Something about you clashes with my book, dear, and I couldn't make you a place. Ask in the Slack and somebody will see about it."),
    "failed": ("That didn't work", "Something went wrong between me and Hack Club, dear, and nothing was saved. Try again in a minute."),
}

# What Grandma says when connecting Hackatime does not go through (accounts/views.py): one fixed label and sentence per case, nothing from Hackatime or
# the request is ever repeated. "taken" is a Hackatime account that already belongs to another account here, or an account here already connected to another one.
HACKATIME_REFUSALS = {
    "taken": ("Already spoken for", "That Hackatime account is down in my book for somebody else, dear, or you have already given me a different one. One Hackatime account for each of you. Ask in the Slack and somebody will see about it."),
    "failed": ("That didn't work", "Something went wrong between me and Hackatime, dear, and nothing was saved. Try again in a minute."),
}
