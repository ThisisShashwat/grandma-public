"""A dialogue is data: a list of steps Grandma goes through one at a time. No Django import in this file.

    Say(lines=...)                         Grandma talks, the person taps "go on"
    AskText(key=..., lines=...)            Grandma asks for a line of text
    AskChoice(key=..., choices=...)        Grandma asks, the person taps one answer
    End(lines=...)                         the last word, with a button to somewhere else

Every step can carry `face` (one of Grandma's faces or poses, talk/portraits.py) and `when`, a function of the answers
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
    button: str = "That's me"


@dataclass(frozen=True, kw_only=True)
class AskChoice(Step):
    key: str
    choices: tuple               # (value, label) pairs


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


def fill(line, answers):
    """A line with its {key} placeholders filled from the answers. An unanswered key is an empty string."""
    return line.format_map(defaultdict(str, answers))
