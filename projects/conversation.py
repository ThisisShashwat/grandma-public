"""Talk to Grandma at /grandma/: the dialogue for one person and where its answers go. Her words are projects/script.py, the
framework is talk/, everything that changes a project is projects/services.py.

The project is made the moment the four questions are answered, and the hand is dealt and saved on it then, so the hand
is in the database and a refresh, a second tab or a new session shows the same notes: nothing is re-rolled by asking again.
The person's place in the dialogue is in the session as for any dialogue, but the database wins: with a hand on the go they
are always at the notes. Keeping notes happens inside the store's save (before the place moves on), so a refused choice
leaves everything where it was.
"""
from dataclasses import replace

from django.urls import reverse
from django.utils import timezone

from accounts.services import profile_of
from accounts.validators import validate_polite_name
from projects import expiry, notes, rules, script, services
from projects.models import Demand
from projects.validators import validate_idea, validate_project_name
from talk.dialogue import Deal, End, State
from talk.store import SessionStore


def cookies(amount):
    """'no cookies', '1 cookie', '10 cookies': how Grandma says an amount."""
    return "no cookies" if amount == 0 else f"{amount} cookie" + ("" if amount == 1 else "s")


def again_for(project, cfg):
    """What the Deal step's "deal again" button needs: the next re-deal's number, how many free ones are left, its price, and
    where the button goes."""
    return rules.offer(project.redeals_used, cfg.REDEALS_FREE, cfg.REDEAL_COST)._asdict() | {"url": reverse("grandma_again")}


def deal_step(user, cfg):
    """The notes on the table, taken from the person's dealing project (none: an apology instead, never a crash)."""
    project = services.dealing_project(user)
    fitting = services.hand_demands(project) if project else []
    hand = notes.notes(fitting) if fitting else []
    has_category_demands = Demand.objects.filter(categories=project.category, active=True).exists() if project else False
    if not hand:
        lines = script.NO_FITTING_NOTES if has_category_demands else script.EMPTY_JAR
    else:
        lines = script.DEAL.lines
    return replace(script.DEAL, lines=lines, notes=lambda: hand,
                   again=(lambda: again_for(project, cfg)) if (hand or has_category_demands) and project else None,
                   edit_url=reverse("project_edit"))


def dialogue(cfg, user):
    """The whole conversation as a list of steps, for the admin settings in `cfg` (pages.live.live()) and this person."""
    expiry.expire_stale(user, days=cfg.DEALING_EXPIRY_DAYS)         # a hand left on the table for too long is gone before anything reads it
    return [
        *script.INTRO,
        replace(script.ASK_IDEA, validators=(validate_idea,)), script.SAID_IDEA,
        replace(script.ASK_NAME, validators=(validate_project_name, validate_polite_name)), script.SAID_NAME,
        replace(script.ASK_CATEGORY, choices=lambda answers: services.category_choices()),
        replace(script.ASK_SUBCATEGORY, choices=lambda answers: services.subcategory_choices(answers.get("category")),
                when=lambda answers: bool(services.subcategory_choices(answers.get("category")))),
        deal_step(user, cfg),
        script.ENDING,
    ]


def edit_dialogue(project):
    """The 5-step conversation to edit a working project's idea, name, category, and subcategory."""
    return [
        replace(script.EDIT_IDEA, validators=(validate_idea,)),
        replace(script.EDIT_NAME, validators=(validate_project_name, validate_polite_name)),
        replace(script.ASK_CATEGORY, lines=script.EDIT_CATEGORY_LINES, choices=lambda answers: services.category_choices()),
        replace(script.ASK_SUBCATEGORY, choices=lambda answers: services.subcategory_choices(answers.get("category")),
                when=lambda answers: bool(services.subcategory_choices(answers.get("category")))),
        script.EDIT_SAVED,
    ]


def demands_dialogue(project, cfg):
    """The 2-step conversation to change demands for a building project."""
    return [
        replace(script.DEMANDS_DEAL, notes=lambda: notes.notes(services.hand_demands(project)),
                again=lambda: again_for(project, cfg)),
        script.DEMANDS_SAVED,
    ]


class EditStore(SessionStore):
    """Answers prefilled from project; save calls edit_project at the End step before session write."""

    def __init__(self, steps, project):
        super().__init__("project_edit")
        self.project = project
        self.end_at = next(i for i, step in enumerate(steps) if isinstance(step, End))

    def load(self, request):
        state = super().load(request)
        person = {"display_name": profile_of(request.user).display_name}
        cat_value = self.project.category.slug
        sub_value = str(self.project.subcategory.pk) if self.project.subcategory else ""
        initial = {"idea": self.project.idea, "name": self.project.name, "category": cat_value, "subcategory": sub_value}
        answers = initial | state.answers | person
        return State(state.position, answers)

    def save(self, request, state):
        if state.position >= self.end_at:
            answers = state.answers
            services.edit_project(
                request.user,
                idea=answers.get("idea", ""),
                name=answers.get("name", ""),
                category_value=answers.get("category", ""),
                subcategory_value=answers.get("subcategory", ""),
            )
        super().save(request, state)


class DemandsStore(SessionStore):
    """Current kept demands prefilled; save calls rekeep when Deal step is answered before session write."""

    def __init__(self, steps, project):
        super().__init__("project_demands")
        self.project = project
        self.deal_at = next(i for i, step in enumerate(steps) if isinstance(step, Deal))
        self.end_at = next(i for i, step in enumerate(steps) if isinstance(step, End))

    def load(self, request):
        state = super().load(request)
        person = {"display_name": profile_of(request.user).display_name}
        kept_ids = [str(d.id) for d in services.kept_demands(self.project)]
        initial = {"keep": kept_ids}
        answers = initial | state.answers | person
        return State(state.position, answers)

    def save(self, request, state):
        if state.position > self.deal_at:
            services.rekeep(request.user, state.answers.get("keep", []), timezone.now())
        super().save(request, state)


class Store(SessionStore):
    """The place in the dialogue is in the session; the project, the hand and the kept notes are in the database."""

    def __init__(self, steps, cfg, rng):
        super().__init__("grandma")
        self.deal_at = next(i for i, step in enumerate(steps) if isinstance(step, Deal))
        self.end_at = self.deal_at + 1
        self.cfg, self.rng = cfg, rng

    def load(self, request):
        state = super().load(request)
        person = {"display_name": profile_of(request.user).display_name}    # always fresh from the Profile, so her lines can use it
        project = services.working_project(request.user)
        if project is None:                       # nothing dealt yet: questions in progress (a stale finished place starts over)
            return State(state.position, state.answers | person) if state.position < self.deal_at else State(0, person)
        answers = {"idea": project.idea, "name": project.name} | state.answers | person
        if project.status == rules.DEALING:       # a hand is on the table: always at the notes, from any session
            return State(self.deal_at, answers)
        return State(state.position, answers)

    def save(self, request, state):
        if state.position == self.deal_at:        # the last question was just answered: make the project and deal
            answers = state.answers
            category, subcategory = services.resolve(answers.get("category", ""), answers.get("subcategory", ""))
            services.start(request.user, idea=answers.get("idea", ""), name=answers.get("name", ""), category=category,
                           subcategory=subcategory, size=self.cfg.DEAL_SIZE, rng=self.rng)
        elif state.position > self.deal_at:       # the notes were kept
            services.keep(request.user, state.answers.get("keep", []), timezone.now())
        super().save(request, state)


def sent_away(request, store):
    """Someone with a project under way (confirmed, not still dealing) does not talk to Grandma again: they go to their project,
    except in the session that has just confirmed, which still gets her send-off."""
    project = services.working_project(request.user)
    return project is not None and project.status != rules.DEALING and store.load(request).position < store.end_at
