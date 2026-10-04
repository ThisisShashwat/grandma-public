"""Grandma hands over the result of a review (/grandma/collect/). Cookies never arrive by themselves: after a reviewer has decided,
the person's next visit to a page that matters sends them to her first (`PAGES`, the middleware), she reads the reviewer's note, and the
cookies go on the ledger when they take them. Her words are submissions/script.py, the framework is talk/, the ledger write is
services.claim (once, whatever happens: a double click, a reload, two tabs).

The claim happens inside the store's save, before the person's place in the session moves on, so a failure can never leave
someone standing at the last page with nothing handed over. Until a submission is claimed the person cannot be past the step that
claims it, whatever the session says."""
from django.urls import reverse

from accounts.services import profile_of
from projects.conversation import cookies
from submissions import rules, script, services
from submissions.models import Submission
from talk.dialogue import State
from talk.store import SessionStore

SESSION = "collect"

#: The pages that matter, by URL name: a person with a result waiting at Grandma's is sent to her before any of them
#: (submissions/middleware.py), on every visit, until they have collected it.
PAGES = ("dashboard", "dashboard_submissions", "dashboard_cookies", "project", "grandma", "submit", "submit_fix", "project_edit", "project_demands")


def outcome(submission, max_rounds):
    approved = submission.status == rules.APPROVED
    mood = rules.mood(services.tiers_of(submission.project), submission.approved_hours, submission.quality, submission.ribbon) if approved else "sideeye"
    return script.Outcome(approved=approved, ribbon=approved and submission.ribbon,
                          cookies=submission.cookies_awarded or 0, has_note=bool(submission.public_note.strip()), mood=mood,
                          changes=submission.status == rules.CHANGES_REQUESTED, goes_left=max_rounds - submission.round)


def dialogue(cfg, submission):
    """The steps for this result, for the admin settings in `cfg` (pages.live.live(): MAX_ROUNDS says how many goes are left)."""
    return script.conversation(outcome(submission, cfg.MAX_ROUNDS))


def then(submission):
    """Where the send-off leads: the fix page of a project with changes requested, else the dashboard."""
    return reverse("submit_fix", args=[submission.project_id]) if submission.status == rules.CHANGES_REQUESTED else reverse("dashboard")


def answers(submission):
    """What her lines quote: the person's name, the project's name, the reviewer's note and the amount. Always fresh from the database."""
    return {"submission": str(submission.pk), "display_name": profile_of(submission.project.user).display_name, "name": submission.project.name, "note": submission.public_note.strip(), "cookies": cookies(submission.cookies_awarded or 0)}


def current(request):
    """The submission being handed over: the oldest one waiting, or the one this session has just collected (its last page, the
    send-off, is still to be seen). None when there is nothing to show."""
    waiting = services.waiting(request.user)
    if waiting:
        return waiting
    shown = request.session.get(f"talk:{SESSION}", {}).get("answers", {}).get("submission", "")
    if not (str(shown).isascii() and str(shown).isdigit()):
        return None
    return Submission.objects.filter(pk=shown, project__user=request.user, claimed_at__isnull=False).select_related("project").first()


class Store(SessionStore):
    """The place in the conversation is in the session; the claim is in the database."""

    def __init__(self, submission, steps):
        super().__init__(SESSION)
        self.submission, self.base, self.end_at = submission, answers(submission), len(steps) - 1

    def load(self, request):
        saved = super().load(request)
        if saved.answers.get("submission") != self.base["submission"]:       # a different result than last time: start from the top
            return State(0, dict(self.base))
        position = saved.position if self.submission.claimed_at else min(saved.position, self.end_at - 1)
        return State(position, saved.answers | self.base)

    def save(self, request, state):
        if state.position >= self.end_at:                                     # the last question was just answered: hand it over
            services.claim(request.user, self.submission.pk)
        super().save(request, state)
