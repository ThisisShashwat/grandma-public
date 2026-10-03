"""What Grandma says when someone talks to her about a project. Text and steps only; the wiring (where the choices come from,
where answers go) is projects/conversation.py. Original wording in her voice: no dollars, no rates, only cookies."""
from talk.dialogue import AskChoice, AskText, Deal, End, Say

INTRO = [
    Say(face="wave", lines=(
        "Ah. A visitor. Sit down, dear, and mind the cat. She bites.",
        "You've come about a project. Good. I've been waiting all week for somebody to boss about.")),
    Say(face="finger", lines=(
        "Here's the arrangement. You tell me what you're making. That part is yours: I wouldn't dream of choosing.",
        "Then I rummage in my cookie jar and deal you a handful of demands. Silly rules about how you build it.")),
    Say(face="sideeye", lines=(
        "You keep one, two or three. Never none, I'm not a charity. Never four, I'm not a saint.",
        "Don't like your hand? I'll deal again. The first few times are free. After that it costs cookies, because the jar doesn't refill itself.")),
]

ASK_IDEA = AskText(key="idea", face="writing", label="What you're going to make", max_length=200,
                   attrs={"autocomplete": "off", "spellcheck": "true"}, lines=(
                       "So. What are you going to make, dear?",
                       "A sentence will do. 'A weather station that sulks when it rains' is the sort of thing I enjoy."))
SAID_IDEA = Say(face="smug", lines=("{idea}.", "Hm. Everybody starts somewhere."))

ASK_NAME = AskText(key="name", face="clipboard", label="Project name", max_length=40,
                   attrs={"autocomplete": "off", "spellcheck": "false"}, lines=(
                       "Every project needs a name, same as a cat.", "What are we calling it?"))
SAID_NAME = Say(face="eyeroll", lines=("{name}.", "I'd have gone shorter. But nobody asked me. I'll put it on the fridge."))

# `choices` is filled in per request from the database (conversation.py)
ASK_CATEGORY = AskChoice(key="category", face="phone", choices=(), lines=(
    "What sort of thing is it?", "Pick the closest. I'm not fussy. (I am very fussy.)"))
ASK_SUBCATEGORY = AskChoice(key="subcategory", face="magnifier", choices=(), lines=(
    "And a bit more exactly?", "Squint. Pick whichever fits least badly."))

# `notes` and `again` are filled in per request from the person's project (conversation.py)
DEAL = Deal(key="keep", face="note", notes=list, lines=(
    "Right. Hold still while I rummage in the jar.",
    "There. The little face on each note is how I'd feel about you taking it. The happier I look, the more I think of you.",
    "Keep one, two or three. Don't like them? Ask me to deal again."))
EMPTY_JAR = ("My jar is empty for that kind of project, dear, which is not your fault.", "Tell the staff in the Slack. Somebody forgot to fill it.")


ENDING = End(face="approved", button="Show me my project", lines=(
    "{name}. Good. Build it.", "Take as long as it needs, dear. Half an hour or ten days, I'm in no hurry. I will be watching.", "Now off you go. And wipe your feet."))


# the re-deal confirmation page; {cost} and {balance} are filled with "10 cookies" and the like (conversation.cookies)
TOO_POOR = ("{cost}, dear, and you have {balance}. I don't do credit.",
            "Keep one of the notes I dealt you, or go and earn a few more cookies and come back.")
ASK_AGAIN = ("Another deal? So my notes aren't good enough for you.", "That'll be {cost}, dear. You have {balance}.", "Sure about it?")
