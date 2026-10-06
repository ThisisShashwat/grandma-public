"""What Grandma says when someone talks to her about a project. Text and steps only; the wiring (where the choices come from,
where answers go) is projects/conversation.py. Original wording in her voice: no dollars, no rates, only cookies."""
from talk.dialogue import AskChoice, AskText, Deal, End, Say

INTRO = [
    Say(face="wave", lines=(
        "Ah, {display_name}. Sit down, dear, and mind the cat. She bites.",
        "You've come about a project. Good. I've been waiting all week for somebody to boss about.")),
    Say(face="finger", lines=(
        "Here's the arrangement. You tell me what you're making. That part is yours: I wouldn't dream of choosing.",
        "Then I rummage in my cookie jar and deal you a handful of demands. Silly rules about how you build it.")),
    Say(face="sideeye", lines=(
        "You keep one, two or three. Never none, I'm not a charity. Never four, I'm not a saint.",
        "Don't like your hand? I'll deal again. The first few times are free. After that it costs cookies, because the jar doesn't refill itself.")),
]

ASK_IDEA = AskText(key="idea", face="writing", label="What you're going to make", max_length=200, button="That's the idea",
                   attrs={"autocomplete": "off", "spellcheck": "true"}, lines=(
                       "So, {display_name}. What are you going to make?",
                       "A sentence will do. 'A weather station that sulks when it rains' is the sort of thing I enjoy."))
SAID_IDEA = Say(face="smug", lines=("{idea}.", "Hm. Everybody starts somewhere, {display_name}."))

ASK_NAME = AskText(key="name", face="clipboard", label="Project name", max_length=40, button="That's the name",
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
    "Right, {display_name}. Hold still while I rummage in the jar.",
    "There. The little face on each note is how I'd feel about you taking it. The happier I look, the more I think of you.",
    "Keep one, two or three. Don't like them? Ask me to deal again."))
DEAL_NO_AGAIN = (*DEAL.lines[:-1], "Keep one, two or three. That's all I have for that kind of project, dear.")     # no button to deal again (conversation.py)
NOTHING_NEW = End(face="sideeye", button="Back to my notes")       # the page of a refused re-deal: she says services.NOTHING_NEW
EMPTY_JAR = ("My jar is empty for that kind of project, dear, which is not your fault.", "Tell the staff in the Slack. Somebody forgot to fill it.")


ENDING = End(face="approved", button="Show me my project", lines=(
    "{name}. Good. Build it.", "Take as long as it needs, dear. Half an hour or ten days, I'm in no hurry. I will be watching.", "Now off you go, {display_name}. And wipe your feet."))


# the re-deal confirmation page; {cost} and {balance} are filled with "10 cookies" and the like (conversation.cookies)
TOO_POOR = ("{cost}, dear, and you have {balance}. I don't do credit.",
            "Keep one of the notes I dealt you, or go and earn a few more cookies and come back.")
ASK_AGAIN = ("Another deal? So my notes aren't good enough for you.", "That'll be {cost}, dear. You have {balance}.", "Sure about it?")

# editing a project after the hand is dealt
EDIT_IDEA = AskText(key="idea", face="writing", label="What you're going to make", max_length=200, button="That's the idea",
                    attrs={"autocomplete": "off", "spellcheck": "true"}, lines=(
                        "Changed your mind, {display_name}? That's allowed. Nobody has to build the first thing they said.",
                        "So what are you making now?"))
EDIT_NAME = AskText(key="name", face="clipboard", label="Project name", max_length=40, button="That's the name",
                    attrs={"autocomplete": "off", "spellcheck": "false"}, lines=("And what are we calling it?",))
EDIT_CATEGORY_LINES = (
    "What sort of thing is it now?",
    "The notes I dealt you stay the notes you get. Any that don't suit the new kind, I'll cross out.")
EDIT_SAVED = End(face="approved", button="Carry on", lines=(
    "There. I've crossed out the old and written in the new, {display_name}.",
    "The notes I dealt you are the notes you get. I don't hand out new ones for free."))
RENAME_NAME = AskText(key="name", face="clipboard", label="Project name", max_length=40, button="That's the name",
                      attrs={"autocomplete": "off", "spellcheck": "false"}, lines=(
                          "A new name, {display_name}? Fine. Only the name, mind. Your idea, your kind and your demands stay exactly as they are.",
                          "So what are we calling it?"))
RENAME_SAVED = End(face="approved", button="Back to my project", lines=(
    "There. I've crossed out the old name and written in the new one.",
    "Nothing else changed, dear. Not a single demand."))
DEMANDS_DEAL = Deal(key="keep", face="note", notes=list, lines=(
    "Swapping demands, {display_name}? Fine. Pick again from the hand I dealt you.",
    "I won't deal you new ones unless you ask, and asking costs after the free ones."))
DEMANDS_SAVED = End(face="smug", button="Back to my project", lines=(
    "Done. Don't tell me you picked the easy ones because they suit what you built.",
    "I will be checking."))
NO_FITTING_NOTES = (
    "None of the notes I dealt you suit that kind of project, dear.",
    "Ask me to deal again, or go back and change the kind.")
PUT_BACK = "A few of those don't suit that sort of project, dear, so I put them back in the jar. They come back if you change your mind."


def put_back(lines):
    """Her lines with the one about notes that were put back in the jar, just before the last one."""
    return (*lines[:-1], PUT_BACK, lines[-1])
