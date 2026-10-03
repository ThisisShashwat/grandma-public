"""What Grandma says during onboarding. Text and steps only: the questions, the Hackatime step and the two tutorial parts.
Who sees which part is decided in accounts/onboarding.py; how a step is built is talk/dialogue.py."""
from accounts import hackatime
from accounts.validators import suggested_timezones, validate_display_name, validate_slack_id, validate_timezone
from program.content.expertise import EXPERTISE
from program.content.regions import REGIONS
from talk.dialogue import AskChoice, AskText, End, Say

OPENING = [
    Say(face="wave", lines=(
        "Oh! Somebody's here. Come in, come in, and wipe your feet.",
        "I'm Grandma. I'll be bossing you about for the next few weeks, so I need to write a few things down.")),
]

QUESTIONS = [
    AskText(key="display_name", face="writing", label="Your name", validators=(validate_display_name,), max_length=30,
            attrs={"autocomplete": "nickname", "autocapitalize": "words", "spellcheck": "false"}, lines=(
                "First things first. What should I call you, dear?",
                "Pick a name you don't mind other people seeing. It goes on my wall.")),
    Say(face="smug", lines=("{display_name}.", "Hm. I've heard worse.")),
    AskText(key="slack_id", face="magnifier", label="Slack member ID, like U01ABC23DEF", validators=(validate_slack_id,), max_length=12,
            attrs={"autocomplete": "off", "autocapitalize": "characters", "spellcheck": "false"}, lines=(
                "Now your Slack ID. Not your username, dear. Your ID.",
                "Open your profile in Slack, tap the three dots and pick Copy member ID. It starts with a U or a W.")),
    AskChoice(key="region", face="phone", choices=tuple(REGIONS), lines=(
        "Where in the world are you?", "I need to know how far I have to shout.")),
    AskText(key="timezone", face="clipboard", label="Time zone, like Asia/Kolkata", validators=(validate_timezone,), max_length=64,
            prefill="timezone", suggestions=suggested_timezones, attrs={"autocomplete": "off", "autocapitalize": "off", "spellcheck": "false"}, lines=(
                "And your time zone, so I don't phone you at silly o'clock.",
                "Your browser usually knows. I've asked it nicely.")),
    AskChoice(key="expertise", face="eyeroll", choices=tuple(EXPERTISE), lines=(
        "How much of this have you done before?", "Be honest. I can tell.")),
]

def hackatime_step():
    """SEAM: the Hackatime connection plugs in here (accounts/hackatime.py). Until it exists the button is greyed out and
    the step lets people carry on. Flipping `hackatime.AVAILABLE` without writing the real step fails loudly on purpose."""
    if hackatime.AVAILABLE:
        raise NotImplementedError("Hackatime is marked available: replace the greyed-out button with the connect link (accounts/hackatime.py).")
    return Say(face="finger", disabled="Connect Hackatime", lines=(
        "Now the important bit.",
        "I count your hours with a thing called Hackatime. No Hackatime, no hours. No hours, no cookies.",
        "Press the button and we'll hook you up. ...Oh. It's not ready. Whoever built this place hasn't plugged it in yet. Carry on, dear, we'll come back to it."))


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
        "Then you build it, dear. Ten to fifteen days, all on your own. Hackatime counts your hours while you type.",
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
