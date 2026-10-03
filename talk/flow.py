"""Runs a dialogue as ordinary forms. GET shows the step the person is on, POST answers it and redirects back to the same
address, so a refresh or the back button never resubmits and nothing needs JavaScript. The person's place lives in a
store (talk/store.py), never in the page.

    def welcome(request):
        return flow.run(request, steps, store=SessionStore("welcome"), finish=save_it, then=reverse("home"))
"""
from django import forms
from django.core.exceptions import ValidationError
from django.db import transaction
from django.http import HttpResponseNotAllowed
from django.shortcuts import redirect, render

from talk.dialogue import AskChoice, AskText, End, State, fill, next_position
from talk.portraits import portrait

ERROR_FACE = "sideeye"


def run(request, steps, *, store, finish, then, title="Grandma"):
    """Show or answer the current step. `finish(request, answers)` runs once, when the last step before the end is
    answered (inside the same database transaction as the store's save, so it must be safe to run twice). `then` is
    where the person goes when the dialogue is over."""
    if request.method not in ("GET", "HEAD", "POST"):
        return HttpResponseNotAllowed(["GET", "HEAD", "POST"])
    state = store.load(request)
    position = next_position(steps, state.position, state.answers)
    if position >= len(steps):
        return redirect(then)
    step = steps[position]
    if request.method == "POST":
        return answer(request, steps, step, position, state, store=store, finish=finish, then=then, title=title)
    return show(request, step, position, state.answers, None, then, title)


def answer(request, steps, step, position, state, *, store, finish, then, title):
    if request.POST.get("at") != str(position) or isinstance(step, End):    # a stale tab or a double click: show where we are
        return redirect(request.path)
    form = form_for(step, request.POST, state.answers)
    if form is not None and not form.is_valid():
        return show(request, step, position, state.answers, form, then, title)
    answers = state.answers | ({step.key: form.cleaned_data[step.key]} if form else {})
    ahead = next_position(steps, position + 1, answers)
    try:
        with transaction.atomic():
            store.save(request, State(ahead, answers))
            if ahead >= len(steps) or isinstance(steps[ahead], End):
                finish(request, answers)
    except ValidationError as error:
        if form is None:
            raise
        form.add_error(step.key, messages_for(error, step.key))
        return show(request, step, position, state.answers, form, then, title)
    return redirect(request.path)


def messages_for(error, key):
    """The messages of a ValidationError that belong to this step's answer (a model's error comes keyed by field)."""
    if not hasattr(error, "error_dict"):
        return error.messages
    return error.message_dict.get(key) or [m for messages in error.message_dict.values() for m in messages]


def form_for(step, data, answers):
    """A one-field form that validates a text or choice answer. None for steps that ask nothing."""
    if isinstance(step, AskText):
        field = forms.CharField(max_length=step.max_length, validators=list(step.validators),
                                error_messages={"required": "Say something, dear. I can't write down nothing."})
    elif isinstance(step, AskChoice):
        field = forms.ChoiceField(choices=step.choices, error_messages={
            "required": "Pick one, dear.", "invalid_choice": "That is not one of the choices, dear."})
    else:
        return None
    form = forms.Form(data, initial={step.key: answers.get(step.key, "")})
    form.fields[step.key] = field
    return form


def show(request, step, position, answers, form, then, title):
    face = ERROR_FACE if form is not None and form.errors else step.face
    file, alt = portrait(face)
    if form is None:
        form = form_for(step, None, answers)
    suggestions = getattr(step, "suggestions", ())
    return render(request, "pages/talk.html", {
        "title": title, "step": step, "kind": type(step).__name__.lower(), "at": position, "then": then,
        "lines": [fill(line, answers) for line in step.lines], "portrait": {"file": file, "alt": alt},
        "field": form[step.key] if form is not None else None,
        "suggestions": list(suggestions() if callable(suggestions) else suggestions),
    })
