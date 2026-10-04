"""What Grandma says during onboarding. Text and steps only: the questions, the Hackatime step and the two tutorial parts.
Who sees which part is decided in accounts/onboarding.py; how a step is built is talk/dialogue.py."""
from django.urls import reverse

from accounts.validators import suggested_timezones, validate_display_name, validate_slack_id, validate_timezone
from program.content.expertise import EXPERTISE
from program.content.regions import REGIONS
from talk.dialogue import AskChoice, AskText, End, Say

OPENING = [
    Say(face="wave", lines=(
        "Oh! Somebody's here. Come in, come in, and wipe your feet.",
        "I'm Grandma. I'll be bossing you about for a good while, so I need to write a few things down.")),
]

QUESTIONS = [
    AskText(key="display_name", face="writing", label="Your name", validators=(validate_display_name,), max_length=30, button="That's me",
            attrs={"autocomplete": "nickname", "autocapitalize": "words", "spellcheck": "false"}, lines=(
                "First things first. What should I call you, dear?",
                "Pick a name you don't mind other people seeing. It goes on my wall.")),
    Say(face="smug", lines=("{display_name}.", "Hm. I've heard worse.")),
    AskText(key="slack_id", face="magnifier", label="Slack member ID, like U01ABC23DEF", validators=(validate_slack_id,), max_length=12,
            button="That's my ID", attrs={"autocomplete": "off", "autocapitalize": "characters", "spellcheck": "false"}, lines=(
                "Now your Slack ID, {display_name}. Not your username. Your ID.",
                "Open your profile in Slack, tap the three dots and pick Copy member ID. It starts with a U or a W.")),
    AskChoice(key="region", face="phone", choices=tuple(REGIONS), lines=(
        "Where in the world are you, {display_name}?", "I need to know how far I have to shout.")),
    AskText(key="timezone", face="clipboard", label="Time zone, like Asia/Kolkata", validators=(validate_timezone,), max_length=64,
            prefill="timezone", suggestions=suggested_timezones, button="That's my zone", attrs={"autocomplete": "off", "autocapitalize": "off", "spellcheck": "false"}, lines=(
                "And your time zone, so I don't phone you at silly o'clock.",
                "Your browser usually knows. I've asked it nicely.")),
    AskChoice(key="expertise", face="eyeroll", choices=tuple(EXPERTISE), lines=(
        "How much of this have you done before?", "Be honest. I can tell.")),
]

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
        "Press the button and Hackatime will ask if I may take a look. Its screen lists more than I need, and I can't help that. I keep one number, dear, and hand the key straight back."))


SKIP_OFFER = AskChoice(
    key="tutorial", face="sideeye", choices=(("skip", "No thanks, I know my way around"), ("show", "Fine, lecture me")), lines=(
        "You ship all the time? Show-off.", "I have two little lessons about how things work here. Want them?"))

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
    Say(face="approved", lines=(
        "And that's everything. Questions go in the Slack.", "Somebody there is much less grumpy than me.")),
]

ENDING = End(face="overjoyed", button="Take me home", lines=(
    "{display_name}, you're all set.", "Off you go. And wipe your feet on the way out."))

# What Grandma says when a Hack Club sign-in does not go through (accounts/views.py): one fixed label and sentence per case, so nothing from Hack Club
# or the request is ever repeated. A refusal for an inactive user, a clash of ids and no account at all all get "no_account".
HCA_REFUSALS = {
    "pending": ("Not quite yet", "Hack Club is still looking over your verification, dear. Give them a little time, then come and try again."),
    "not_verified": ("Not verified yet", "Hack Club doesn't have you down as verified yet, dear. Sort that out with them first, then come and try again."),
    "not_eligible": ("Not this time", "Hack Club doesn't have you down as eligible for a program like mine, dear. That's their rule, not mine."),
    "no_slack_id": ("No Slack ID", "Hack Club didn't tell me your Slack ID, dear, and that's how I find you in my book. Join the Hack Club Slack, then try again."),
    "no_account": ("No place at the table", "I can't find a place for you in my book, dear. Accounts here are made by hand, so ask in the Slack and somebody will see about it."),
    "failed": ("That didn't work", "Something went wrong between me and Hack Club, dear, and nothing was saved. Try again in a minute."),
}

# What Grandma says when connecting Hackatime does not go through (accounts/views.py): one fixed label and sentence per case, nothing from Hackatime or
# the request is ever repeated. "taken" is a Hackatime account that already belongs to another account here, or an account here already connected to another one.
HACKATIME_REFUSALS = {
    "taken": ("Already spoken for", "That Hackatime account is down in my book for somebody else, dear, or you have already given me a different one. One Hackatime account for each of you. Ask in the Slack and somebody will see about it."),
    "failed": ("That didn't work", "Something went wrong between me and Hackatime, dear, and nothing was saved. Try again in a minute."),
}
