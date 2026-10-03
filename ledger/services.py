"""The only code that writes the cookie ledger. Every write runs in one transaction that first locks the person's Profile row
(select_for_update), so two requests for the same person never read the same balance, and refuses to go below zero. Posting
a key twice writes once. Rules and maths: ledger/rules.py."""
from django.db import transaction
from django.db.models import Q, Sum

from accounts.models import Profile
from accounts.services import profile_of
from ledger import rules
from ledger.models import CookieEntry


def balance(user):
    return CookieEntry.objects.filter(user=user).aggregate(total=Sum("amount"))["total"] or 0


EARNED = Q(kind=rules.EARNING, amount__gt=0)      # what counts as earned: spending, refunds and adjustments do not


def earned_total(user):
    """Everything this person has ever earned: the positive earning entries only (spending, refunds and adjustments do
    not count). For the all-time leaderboard."""
    return CookieEntry.objects.filter(EARNED, user=user).aggregate(total=Sum("amount"))["total"] or 0


def earned_totals(users):
    """`earned_total` for every person in `users` (a User queryset) who has earned anything, in ONE query: rows of
    {"user": id, "total": n}, the most first, ties by user id so the order never wobbles. Nobody with 0 is in it."""
    return CookieEntry.objects.filter(EARNED, user__in=users).values("user").annotate(total=Sum("amount")).order_by("-total", "user")


def credit(user, amount, *, reason, key, kind=rules.EARNING, by=None):
    """Give `amount` cookies (a positive whole number), as an earning or a refund."""
    return post(CookieEntry(user=user, amount=amount, kind=kind, reason=reason, key=key, created_by=by))


def debit(user, amount, *, reason, key, kind=rules.SPENDING, by=None):
    """Take `amount` cookies (a positive whole number). Raises InsufficientCookies rather than go below zero."""
    return post(CookieEntry(user=user, amount=-amount, kind=kind, reason=reason, key=key, created_by=by))


def adjust(user, amount, *, reason, key, by):
    """A staff correction, positive or negative, by a named staff member."""
    return post(CookieEntry(user=user, amount=amount, kind=rules.ADJUSTMENT, reason=reason, key=key, created_by=by))


@transaction.atomic
def post(entry):
    """Write an unsaved entry (or return the one already written under its key). The entry is saved in place."""
    rules.check(entry.kind, entry.amount, entry.reason, entry.key)
    profile_of(entry.user)
    Profile.objects.select_for_update().get(user=entry.user)         # the lock
    written = CookieEntry.objects.filter(user=entry.user, key=entry.key).first()
    if written:
        if (written.amount, written.kind) != (entry.amount, entry.kind):
            raise ValueError(f"The key {entry.key!r} was already used for a different entry.")
        return written
    if rules.overdraws(balance(entry.user), entry.amount):
        raise rules.InsufficientCookies(f"{entry.user} cannot afford {-entry.amount} cookies.")
    entry.save()
    return entry
