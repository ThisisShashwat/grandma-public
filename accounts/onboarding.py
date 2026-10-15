"""Onboarding at /welcome/: the dialogue, who sees how much tutorial, and where the answers are kept."""
from dataclasses import replace

from django.db import transaction
from django.utils import timezone

from accounts import hackatime, identity, script
from accounts.models import FILLED_IN
from accounts.validators import canonical_timezone, polite_unless, validate_display_name
from accounts.services import profile_of, request_profile
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
    """The tutorial depth the admin settings give this level of experience. Anything unexpected gets the Hack Club basics."""
    return {"new": cfg.TUTORIAL_FOR_NEW, "some": cfg.TUTORIAL_FOR_SOME, "veteran": cfg.TUTORIAL_FOR_VETERAN}.get(expertise, "play")


def plays(part, cfg):
    """A step's `when`: is this tutorial part (0 the Hack Club basics, 1 and 2 about this program) played for the answers so far?"""
    return lambda answers: part in parts(cfg.TUTORIAL_ENABLED, depth_for(answers.get("expertise"), cfg), answers.get("tutorial") == "show")


def asks_to_skip(cfg):
    return lambda answers: offers_skip(cfg.TUTORIAL_ENABLED, depth_for(answers.get("expertise"), cfg))


def question(step, cfg, slack_known, region_guess="", own_names=frozenset()):
    """One question as this site runs it now: the Slack ID is skipped when it is already known, and the regions come from the admin setting (with her
    guess said aloud when the time zone they gave pointed at one: the person still taps their own answer)."""
    key = getattr(step, "key", None)
    if key == "display_name" and own_names:
        return replace(step, validators=(validate_display_name, polite_unless(own_names)))
    if key == "slack_id":
        return replace(step, when=lambda answers: not slack_known)
    if key == "region":
        rows = regions.regions(cfg.REGIONS)
        label = dict(rows).get(region_guess)
        lines = step.lines + (script.region_guess_line(label),) if label else step.lines
        return replace(step, choices=rows, lines=lines, suggested=region_guess if label else "")
    return step


def own_names_of(profile):
    """The names the rude word check lets through for this person: the ones Hack Club gave (the stored identity, accounts/identity.py) and the display name
    a Hack Club account started with. That name is offered back in the box and is theirs (owner, 2026-10-07: never refused), even when no identity is kept."""
    given = {" ".join(profile.display_name.split()).casefold()} if profile.hca_sub and profile.display_name else set()
    return identity.own_names(profile.identity) | given


def dialogue(cfg, hackatime_connected=False, slack_known=False, region_guess="", own_names=frozenset()):
    """The whole of onboarding as a list of steps, for the admin settings in `cfg` (pages.live.live()), whether this person has connected Hackatime and whether their Slack ID is already known.
    The name is always asked: a Hack Club first name is already among the answers (ProfileStore.load), so it is the box's starting value."""
    questions = [question(step, cfg, slack_known, region_guess, own_names) for step in script.QUESTIONS]
    on = hackatime.enabled(cfg)
    return [
        *script.OPENING, script.SOFTWARE_ONLY, *questions,
        *(replace(step, when=plays(1, cfg)) for step in script.PART_ONE),
        *(replace(step, when=plays(2, cfg)) for step in script.PART_TWO),
        script.EXPERIENCE,
        replace(script.SKIP_OFFER, when=asks_to_skip(cfg)),
        *(replace(step, when=plays(0, cfg)) for step in script.PART_BASICS),
        *(replace(step, when=plays(1, cfg)) for step in script.TUTORIAL_CLOSE),
        script.hackatime_step(on, hackatime_connected), script.hackatime_connected_step(on, hackatime_connected),
        script.TALK_FIRST, script.ENDING,
    ]


def finish(cfg, request, answers):
    """Called once, when the last step before the end is answered: they are onboarded. Safe to run twice."""
    profile = request_profile(request)
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
        profile = request_profile(request)
        saved = {key: getattr(profile, key) for key in FILLED_IN if getattr(profile, key)}
        return State(state.position, saved | state.answers)

    def save(self, request, state):
        profile = request_profile(request)
        answers = {key: canonical_timezone(value) if key == "timezone" else value for key, value in state.answers.items()}
        changed = [key for key in FILLED_IN if key in answers and getattr(profile, key) != answers[key]]
        if not changed:                         # most steps are only "go on": nothing to validate or write but the place
            return super().save(request, state)
        for key in FILLED_IN:
            if key in answers:
                setattr(profile, key, answers[key])
        check(profile)        # raises before anything is stored
        with transaction.atomic():
            profile.save()
            if changed:
                audit.record("profile.update", actor=request.user, subject=request.user, target=profile, details={"fields": changed})
        super().save(request, state)
