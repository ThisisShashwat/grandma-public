"""Onboarding at /welcome/: the dialogue, who sees how much tutorial, and where the answers are kept."""
from dataclasses import replace

from django.db import transaction
from django.utils import timezone

from accounts import hackatime, script
from accounts.models import FILLED_IN
from accounts.validators import canonical_timezone
from accounts.services import profile_of
from audit import services as audit
from program.content import regions
from program.tutorial import offers_skip, parts
from talk.dialogue import State
from talk.store import SessionStore


def check(profile):
    """The model's own rules, its constraints and the unique Slack ID. The region is not held to the model's static `choices`: the dialogue's choice
    already checked it against the live REGIONS setting (program/content/regions.py), whose labels staff may change."""
    profile.full_clean(exclude=["user", "region"], validate_constraints=False)
    profile.validate_constraints(exclude=["user"])


def depth_for(expertise, cfg):
    """The tutorial depth the admin settings give this level of experience. Anything unexpected gets the full tutorial."""
    return {"new": cfg.TUTORIAL_FOR_NEW, "some": cfg.TUTORIAL_FOR_SOME, "veteran": cfg.TUTORIAL_FOR_VETERAN}.get(expertise, "both")


def plays(part, cfg):
    """A step's `when`: is this tutorial part (1 or 2) played for the answers so far?"""
    return lambda answers: part in parts(cfg.TUTORIAL_ENABLED, depth_for(answers.get("expertise"), cfg), answers.get("tutorial") == "show")


def asks_to_skip(cfg):
    return lambda answers: offers_skip(cfg.TUTORIAL_ENABLED, depth_for(answers.get("expertise"), cfg))


def question(step, cfg, slack_known, region_guess=""):
    """One question as this site runs it now: the Slack ID is skipped when it is already known, and the regions come from the admin setting (with her
    guess said aloud when the browser pointed at one: the person still taps their own answer)."""
    key = getattr(step, "key", None)
    if key == "slack_id":
        return replace(step, when=lambda answers: not slack_known)
    if key == "region":
        rows = regions.regions(cfg.REGIONS)
        label = dict(rows).get(region_guess)
        lines = step.lines + (script.region_guess_line(label),) if label else step.lines
        return replace(step, choices=rows, lines=lines)
    return step


def dialogue(cfg, hackatime_connected=False, slack_known=False, name_known=False, region_guess=""):
    """The whole of onboarding as a list of steps, for the admin settings in `cfg` (pages.live.live()), whether this person has connected Hackatime, whether their Slack ID is already known, and whether Hack Club already gave their name (the question is then skipped, never removed, so the places in the dialogue never shift)."""
    questions = [question(step, cfg, slack_known, region_guess) for step in script.QUESTIONS]
    questions = [replace(step, when=lambda answers: not name_known) if getattr(step, "key", None) == "display_name" else step for step in questions]
    on = hackatime.enabled(cfg)
    return [
        *script.OPENING, script.SOFTWARE_ONLY, *questions, script.hackatime_step(on, hackatime_connected),
        script.hackatime_connected_step(on, hackatime_connected),
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
    check(profile)
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
        answers = {key: canonical_timezone(value) if key == "timezone" else value for key, value in state.answers.items()}
        changed = [key for key in FILLED_IN if key in answers and getattr(profile, key) != answers[key]]
        for key in FILLED_IN:
            if key in answers:
                setattr(profile, key, answers[key])
        check(profile)        # raises before anything is stored
        with transaction.atomic():
            profile.save()
            if changed:
                audit.record("profile.update", actor=request.user, subject=request.user, target=profile, details={"fields": changed})
        super().save(request, state)
