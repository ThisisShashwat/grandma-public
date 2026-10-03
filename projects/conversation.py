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

from projects import notes, rules, script, services
from projects.validators import validate_idea, validate_project_name
from talk.dialogue import Deal, State
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
    hand = notes.notes(services.hand_demands(project)) if project else []
    return replace(script.DEAL, lines=script.DEAL.lines if hand else script.EMPTY_JAR, notes=lambda: hand,
                   again=(lambda: again_for(project, cfg)) if hand else None)


def dialogue(cfg, user):
    """The whole conversation as a list of steps, for the admin settings in `cfg` (pages.live.live()) and this person."""
    return [
        *script.INTRO,
        replace(script.ASK_IDEA, validators=(validate_idea,)), script.SAID_IDEA,
        replace(script.ASK_NAME, validators=(validate_project_name,)), script.SAID_NAME,
        replace(script.ASK_CATEGORY, choices=lambda answers: services.category_choices()),
        replace(script.ASK_SUBCATEGORY, choices=lambda answers: services.subcategory_choices(answers.get("category")),
                when=lambda answers: bool(services.subcategory_choices(answers.get("category")))),
        deal_step(user, cfg),
        script.ending(cfg.PROJECT_MAX_DAYS),
    ]


class Store(SessionStore):
    """The place in the dialogue is in the session; the project, the hand and the kept notes are in the database."""

    def __init__(self, steps, cfg, rng):
        super().__init__("grandma")
        self.deal_at = next(i for i, step in enumerate(steps) if isinstance(step, Deal))
        self.end_at = self.deal_at + 1
        self.cfg, self.rng = cfg, rng

    def load(self, request):
        state = super().load(request)
        project = services.active_project(request.user)
        if project is None:                       # nothing dealt yet: questions in progress (a stale finished place starts over)
            return state if state.position < self.deal_at else State()
        answers = {"idea": project.idea, "name": project.name} | state.answers
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
    project = services.active_project(request.user)
    return project is not None and project.status != rules.DEALING and store.load(request).position < store.end_at
