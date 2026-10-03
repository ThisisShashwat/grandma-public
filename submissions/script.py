"""What Grandma says when she hands over the result of a review. Text and steps only; the wiring (the person's place in it, what
happens when it is over) is submissions/handover.py. Original wording in her voice: cookies and her mood only, never hours,
dollars or rates. {name} is the project's name, {note} what the reviewer wrote for the person, {cookies} "405 cookies":
they are filled from the answers, so a note with braces or markup in it is plain text, never part of a template."""
from dataclasses import dataclass

from talk.dialogue import End, Say


@dataclass(frozen=True)
class Outcome:
    approved: bool
    ribbon: bool
    design: bool       # a hardware design ship: approved means the build ship is next
    cookies: int
    has_note: bool
    mood: str          # the face of her mood, from the payout scale (rules.mood)


def conversation(outcome):
    """The steps for this outcome. The last step before the End is the one that hands over (or turns down): answering it is what collects."""
    opening = Say(face="magnifier", lines=("Ah, there you are, dear. I've been through {name}.", "Every line of it. Even the bits you hoped I'd skip."))
    note = Say(face=outcome.mood if outcome.approved else "sideeye",
               lines=("The reviewer left you a note. I'll read it out, since you can't be trusted to.", "“{note}”") if outcome.has_note
               else ("The reviewer left you no note at all.", "From a reviewer, that is practically a hug."))
    return [opening, note, *(approved(outcome) if outcome.approved else rejected())]


def approved(outcome):
    ribbon = [Say(face="ribbon", celebrate=True, lines=(
        "Wait. Wait, wait, wait.", "That is a Blue Ribbon, dear. I don't give those out.", "Well. I do. But very rarely. Hold still while I pin it on you."))] if outcome.ribbon else []
    pays = outcome.cookies > 0
    hand_over = Say(face="cookie-jar", button="Take the cookies" if pays else "Right, then",
                    lines=("Here. {cookies}.", "Count them. I'll know if you don't.") if pays else ("No cookies for this one, dear.", "But it's through, and I'm not taking back what I said."))
    next_up = "Now build the real thing and hand that in too." if outcome.design else "Come back and show me the next one."
    thanks = "Into your jar they go." if pays and not outcome.ribbon else "Well done, dear."
    return [*ribbon, hand_over, End(face="overjoyed" if outcome.ribbon else "approved", button="To my dashboard", lines=(thanks, next_up))]


def rejected():
    return [Say(face="nose-up", button="I understand", lines=("It's a no this time, dear. No cookies.", "Don't sulk. Fix it, or build me something new and bring it here.")),
            End(face="shush", button="To my dashboard", lines=("Chin up.", "The jar is always open, and so am I. Sort of."))]


# /submit/ when there is nothing to hand in (submissions/views.py not_now)
STILL_READING = ("I'm reading what you handed me, dear.", "Don't hover. I'll tell you when I'm done, and you'll know, because I'll make you come and see me.")
NOTHING_TO_HAND_IN = ("You've nothing on the go, dear.", "Come and talk to me about a new project. Then you'll have something to hand in.")
