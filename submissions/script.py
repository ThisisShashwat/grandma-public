"""What Grandma says when she hands over the result of a review. Text and steps only; the wiring (the person's place in it, what
happens when it is over) is submissions/handover.py. Original wording in her voice: cookies and her mood only, never hours,
dollars or rates. {display_name} is the person's name, {name} the project's name, {note} what the reviewer wrote for the person, {cookies} "405 cookies":
they are filled from the answers, so a note with braces or markup in it is plain text, never part of a template."""
from dataclasses import dataclass

from talk.dialogue import End, Say


@dataclass(frozen=True)
class Outcome:
    approved: bool
    ribbon: bool
    cookies: int
    has_note: bool
    mood: str          # the face of her mood, from the payout scale (rules.mood)
    changes: bool = False      # the reviewer asked for changes: nothing paid, and the person can fix it and hand it in again
    goes_left: int = 0         # hand-ins still allowed after this round (MAX_ROUNDS minus the round): 1 or less means the next one is the last go


def conversation(outcome):
    """The steps for this outcome. The last step before the End is the one that hands over (or turns down): answering it is what collects."""
    opening = Say(face="magnifier", lines=("Ah, there you are, {display_name}. I've been through {name}.", "Every line of it. Even the bits you hoped I'd skip."))
    note = Say(face=outcome.mood if outcome.approved else "sideeye",
               lines=("The reviewer left you a note. I'll read it out, since you can't be trusted to.", "“{note}”") if outcome.has_note
               else ("The reviewer left you no note at all.", "From a reviewer, that is practically a hug."))
    if outcome.changes:
        return [opening, *changes(outcome)]
    return [opening, note, *(approved(outcome) if outcome.approved else rejected())]


def approved(outcome):
    ribbon = [Say(face="ribbon", celebrate=True, lines=(
        "Wait. Wait, wait, wait.", "That is a Blue Ribbon, dear. I don't give those out.", "Well. I do. But very rarely. Hold still while I pin it on you."))] if outcome.ribbon else []
    pays = outcome.cookies > 0
    hand_over = Say(face="hug", button="Take the cookies" if pays else "Right, then",
                    lines=("Here, {display_name}. {cookies}.", "Count them. I'll know if you don't.") if pays else ("No cookies for this one, dear.", "But it's through, and I'm not taking back what I said."))
    next_up = "Come back and show me the next one."
    thanks = "Into your jar they go." if pays and not outcome.ribbon else "Well done, dear."
    return [*ribbon, hand_over, End(face="overjoyed" if outcome.ribbon else "approved", button="To my dashboard", lines=(thanks, next_up))]


def rejected():
    return [Say(face="nose-up", button="I understand", lines=("It's a no this time, {display_name}. No cookies.", "Don't sulk. Fix it, or build me something new and bring it here.")),
            End(face="shush", button="To my dashboard", lines=("Chin up.", "The jar is always open, and so am I. Sort of."))]


def changes(outcome):
    """The note is what she wants changed, then no cookies yet and how many goes are left; the step that hands over (the claim) is "I'll fix it"."""
    note = Say(face="finger", lines=("The reviewer would like some things changed, {display_name}. I'll read it out, since you can't be trusted to.", "“{note}”"))
    hand_over = Say(face="sideeye", button="I'll fix it", lines=(
        "No cookies for this round, dear. Not yet.", "Fix it whenever you like, there is no clock, and bring it back to me.", goes_left_line(outcome.goes_left)))
    return [note, hand_over, End(face="clipboard", button="To the fix page", lines=("Take your time.", "I'll be here when it's ready."))]


def goes_left_line(goes_left):
    """Asked for changes, there is always a next go (a lowered MAX_ROUNDS cannot take it back), so there is never "no goes left"."""
    if goes_left > 1:
        return f"You have {goes_left} goes left."
    return "The next one is your last go. After that I say yes or no, and nothing in between."


# /submit/ when there is nothing to hand in (submissions/views.py not_now)
STILL_READING = ("I'm reading what you handed me, dear.", "Don't hover. I'll tell you when I'm done, and you'll know, because I'll make you come and see me.", "Meanwhile you can talk to me about a new one.")
NOTHING_TO_HAND_IN = ("You've nothing on the go, dear.", "Come and talk to me about a new project. Then you'll have something to hand in.")
