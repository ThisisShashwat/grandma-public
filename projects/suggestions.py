"""The suggestion board: people ask for new demands and Pantry items, others vote (docs/projects.md "The suggestion board").

Two kinds, one set of rules and one set of code. Suggesting and voting both cost cookies (admin settings SUGGEST_COST, a little more, and VOTE_COST), taken
through ledger.services.debit under a key made from the suggestion, so a double click can never charge twice. A vote does nothing but move the suggestion
up the list. The board is anonymous: nothing here hands out who suggested what. The spam limit and the lengths are projects/rules.py and the models."""
from dataclasses import dataclass

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import F
from django.utils import timezone

from audit import services as audit
from ledger import services as ledger
from program.profanity import is_rude
from projects import rules
from projects.models import Suggestion, SuggestionVote
from projects.services import lock_person

TOO_MANY = "That's enough suggestions for one day, dear. Give the others a turn. Come back tomorrow."
RUDE = "Not in my kitchen, dear. Say it nicely."
SAID_ALREADY = "You've already put that on the board, dear."
GONE = "That one has gone from the board, dear."
OWN = "You can't vote for your own, dear. Let somebody else do it."
VOTED = "You've already voted for that one, dear."
KINDS = {value for value, _ in rules.SUGGESTION_KINDS}


@dataclass(frozen=True)
class Row:
    """One suggestion as the page may know it: no person, no model."""
    id: int
    title: str
    text: str
    example: str
    votes: int
    age: str
    mine: bool
    voted: bool


def age(created, now=None):
    """'today', 'yesterday' or 'N days ago': enough to tell new from old, and no time zone to get wrong."""
    days = ((now or timezone.now()) - created).days
    return "today" if days < 1 else "yesterday" if days == 1 else f"{days} days ago"


def reason(kind, what):
    """The words in the ledger: no free text a person typed."""
    return f"{what} ({'a demand' if kind == rules.DEMAND else 'a Pantry item'})"


@transaction.atomic
def suggest(user, kind, title, text, example, cost):
    """Put one suggestion on the board and charge `cost` cookies, in one transaction under the person's lock (two clicks cannot both fit under the
    limit or the balance). ValidationError, and nothing written, for an unknown kind, a bad length or character, a rude word, the same title again, or
    more than SUGGESTION_LIMIT in a day; InsufficientCookies, and nothing written, when they cannot pay."""
    if kind not in KINDS:
        raise ValidationError("I don't know what kind of suggestion that is, dear.")
    lock_person(user)
    suggestion = Suggestion(user=user, kind=kind, title=title.strip(), text=rules.tidy(text), example=example.strip())
    suggestion.full_clean()
    if any(is_rude(part) for part in (suggestion.title, suggestion.text, suggestion.example)):
        raise ValidationError(RUDE)
    recent = Suggestion.objects.filter(user=user, created_at__gte=timezone.now() - rules.COMPLAINT_WINDOW)
    if recent.count() >= rules.SUGGESTION_LIMIT:
        raise ValidationError(TOO_MANY)
    if recent.filter(kind=kind, title__iexact=suggestion.title).exists():
        raise ValidationError(SAID_ALREADY)
    suggestion.save()
    if cost:
        ledger.debit(user, cost, reason=reason(kind, "Suggested"), key=f"suggest:{suggestion.pk}")
    audit.record("suggestion.create", actor=user, subject=user, target=suggestion, details={"suggestion": suggestion.pk, "kind": kind, "cost": cost})
    return suggestion


@transaction.atomic
def vote(user, suggestion_id, cost):
    """One vote, charged `cost` cookies, for a suggestion that is on the board and not the person's own, once per person. The vote, the cookies and the
    count move together or not at all; a second try changes nothing and charges nothing (the database refuses the second vote and the ledger key is
    the same). ValidationError for a gone, own or already voted suggestion; InsufficientCookies when they cannot pay."""
    lock_person(user)
    suggestion = Suggestion.objects.select_for_update().filter(pk=suggestion_id, hidden=False).first()
    if suggestion is None:
        raise ValidationError(GONE)
    if suggestion.user_id == user.pk:
        raise ValidationError(OWN)
    if SuggestionVote.objects.filter(suggestion=suggestion, user=user).exists():
        raise ValidationError(VOTED)
    SuggestionVote.objects.create(suggestion=suggestion, user=user)
    if cost:
        ledger.debit(user, cost, reason=reason(suggestion.kind, "Voted"), key=f"suggestion-vote:{suggestion.pk}:{user.pk}")
    Suggestion.objects.filter(pk=suggestion.pk).update(votes=F("votes") + 1)
    audit.record("suggestion.vote", actor=user, subject=user, target=suggestion, details={"suggestion": suggestion.pk, "cost": cost})
    return suggestion


ORDER = {"top": ("-votes", "-created_at", "-id"), "new": ("-created_at", "-id"), "old": ("created_at", "id")}


def board(user, kind, sort="top"):
    """The visible suggestions of one kind, in the order asked for (an unknown order is the top one), as plain rows."""
    chosen = sort if sort in ORDER else "top"
    suggestions = list(Suggestion.objects.filter(kind=kind, hidden=False).order_by(*ORDER[chosen])[:rules.SHOWN])
    voted = set(SuggestionVote.objects.filter(user=user, suggestion__in=suggestions).values_list("suggestion_id", flat=True))
    now = timezone.now()
    return [Row(s.id, s.title, s.text, s.example, s.votes, age(s.created_at, now), s.user_id == user.pk, s.id in voted) for s in suggestions]
