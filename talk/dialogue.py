"""A dialogue is data: a list of steps Grandma goes through one at a time. No Django import in this file.

    Say(lines=...)                         Grandma talks, the person taps "go on"
    AskText(key=..., lines=...)            Grandma asks for a line of text
    AskChoice(key=..., choices=...)        Grandma asks, the person taps one answer
    Deal(key=..., notes=...)               Grandma lays notes on her fridge, the person keeps some of them
    End(lines=...)                         the last word, with a button to somewhere else

Every step can carry `face` (one of Grandma's faces or poses, talk/portraits.py), `celebrate` and `when`, a function of the answers
so far that says whether the step is played at all. A line may hold {key} placeholders, filled from the answers.
Running one is talk/flow.py, how to add one is docs/accounts.md.
"""
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Callable


@dataclass(frozen=True, kw_only=True)
class Step:
    lines: tuple = ()
    face: str = "smug"
    when: Callable[[dict], bool] | None = None
    celebrate: bool = False      # her picture pops in and confetti goes off (static/js/features/celebrate.js), for a Blue Ribbon


@dataclass(frozen=True, kw_only=True)
class Say(Step):
    button: str = "Go on"
    disabled: str = ""           # label of a button that does not work yet, shown greyed out above the real one


@dataclass(frozen=True, kw_only=True)
class AskText(Step):
    key: str
    label: str
    validators: tuple = ()       # callables that raise django.core.exceptions.ValidationError
    max_length: int = 100
    attrs: dict = field(default_factory=dict)       # extra HTML attributes: autocomplete, inputmode, placeholder...
    suggestions: Callable[[], list] | tuple = ()    # offered as a datalist, never enforced (the validators are the rule)
    prefill: str = ""            # name of a browser hint talk.js can fill in when the box is empty ("timezone")
    button: str = "Go on"


@dataclass(frozen=True, kw_only=True)
class AskChoice(Step):
    key: str
    choices: Callable[[dict], tuple] | tuple     # (value, label) pairs, or a function of the answers so far that returns them


@dataclass(frozen=True, kw_only=True)
class Deal(Step):
    """Notes on Grandma's fridge; the person keeps between `min_keep` and `max_keep` of them. `notes()` returns what is on the
    table now (objects with `id` and `name`, shown by templates/macros/notes.html) and is called when the page is drawn and
    when an answer is checked, so the table lives wherever the caller keeps it (the database), never in the page. `again()`
    returns what the "deal again" button needs (templates/components/talk.html) or None for no button."""
    key: str
    notes: Callable[[], list]
    min_keep: int = 1
    max_keep: int = 3
    again: Callable[[], object] | None = None
    button: str = "Keep these"


@dataclass(frozen=True, kw_only=True)
class End(Step):
    button: str = "Off you go"


@dataclass(frozen=True)
class State:
    """Where a person is: the index of the current step and what they have answered so far. Stored by a store."""
    position: int = 0
    answers: dict = field(default_factory=dict)


def next_position(steps, position, answers):
    """The first step at or after `position` that is played for these answers. len(steps) when there is none."""
    while position < len(steps) and steps[position].when is not None and not steps[position].when(answers):
        position += 1
    return position


def previous_position(steps, position, answers):
    """The nearest step before `position` that is played for these answers, or None when there is none. Back goes there."""
    for index in range(position - 1, -1, -1):
        if steps[index].when is None or steps[index].when(answers):
            return index
    return None


def without_skipped(steps, answers):
    """The answers minus those of keyed steps that are not played for them: after Back and a changed answer, a step may now be skipped and its old answer must not linger."""
    stale = {step.key for step in steps if hasattr(step, "key") and step.when is not None and not step.when(answers)}
    return {key: value for key, value in answers.items() if key not in stale}


def choices_for(step, answers):
    """The (value, label) pairs of a choice step for the answers so far."""
    return tuple(step.choices(answers) if callable(step.choices) else step.choices)


def fill(line, answers):
    """A line with its {key} placeholders filled from the answers. An unanswered key is an empty string."""
    return line.format_map(defaultdict(str, answers))
