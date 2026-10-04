"""Onboarding at /welcome/: the dialogue, who sees how much tutorial, and where the answers are kept."""
from dataclasses import replace

from django.db import transaction
from django.utils import timezone

from accounts import hackatime, script
from accounts.models import FILLED_IN
from accounts.services import profile_of
from audit import services as audit
from program.tutorial import offers_skip, parts
from talk.dialogue import State
from talk.store import SessionStore


def depth_for(expertise, cfg):
    """The tutorial depth the admin settings give this level of experience. Anything unexpected gets the full tutorial."""
    return {"new": cfg.TUTORIAL_FOR_NEW, "some": cfg.TUTORIAL_FOR_SOME, "veteran": cfg.TUTORIAL_FOR_VETERAN}.get(expertise, "both")


def plays(part, cfg):
    """A step's `when`: is this tutorial part (1 or 2) played for the answers so far?"""
    return lambda answers: part in parts(cfg.TUTORIAL_ENABLED, depth_for(answers.get("expertise"), cfg), answers.get("tutorial") == "show")


def asks_to_skip(cfg):
    return lambda answers: offers_skip(cfg.TUTORIAL_ENABLED, depth_for(answers.get("expertise"), cfg))


def dialogue(cfg, hackatime_connected=False, slack_known=False):
    """The whole of onboarding as a list of steps, for the admin settings in `cfg` (pages.live.live()), whether this person has connected Hackatime, and whether their Slack ID is already known."""
    questions = [
        replace(step, when=lambda answers: not slack_known) if getattr(step, "key", None) == "slack_id" else step
        for step in script.QUESTIONS
    ]
    return [
        *script.OPENING, script.SOFTWARE_ONLY, *questions, script.hackatime_step(hackatime.enabled(cfg), hackatime_connected),
        replace(script.SKIP_OFFER, when=asks_to_skip(cfg)),
        *(replace(step, when=plays(1, cfg)) for step in script.PART_ONE),
        *(replace(step, when=plays(2, cfg)) for step in script.PART_TWO),
        script.ENDING,
    ]


def finish(cfg, request, answers):
    """Called once, when the last step before the end is answered: they are onboarded. Safe to run twice."""
    profile = profile_of(request.user)
    first_time = not profile.onboarded_at
    profile.onboarded_at = profile.onboarded_at or timezone.now()
    if cfg.TUTORIAL_ENABLED:
        profile.tutorial_done_at = profile.tutorial_done_at or profile.onboarded_at
    profile.full_clean(exclude=["user"])
    with transaction.atomic():
        profile.save()
        if first_time:
            audit.record("onboarding.finish", actor=request.user, subject=request.user, target=profile)


class ProfileStore(SessionStore):
    """The place in the dialogue lives in the session, like any dialogue. Each answer goes into the person's Profile the
    moment it is given, so closing the tab loses nothing but the place (the answers come back as the boxes' starting values)."""

    def __init__(self):
        super().__init__("welcome")

    def load(self, request):
        state = super().load(request)
        profile = profile_of(request.user)
        saved = {key: getattr(profile, key) for key in FILLED_IN if getattr(profile, key)}
        return State(state.position, saved | state.answers)

    def save(self, request, state):
        profile = profile_of(request.user)
        changed = [key for key in FILLED_IN if key in state.answers and getattr(profile, key) != state.answers[key]]
        for key in FILLED_IN:
            if key in state.answers:
                setattr(profile, key, state.answers[key])
        profile.full_clean(exclude=["user"])        # the model's own rules and the unique Slack ID; raises before anything is stored
        with transaction.atomic():
            profile.save()
            if changed:
                audit.record("profile.update", actor=request.user, subject=request.user, target=profile, details={"fields": changed})
        super().save(request, state)
