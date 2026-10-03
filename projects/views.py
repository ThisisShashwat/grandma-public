"""Talk to Grandma (/grandma/, /grandma/again/) and the person's project (/project/). Every page here is for one signed-in,
onboarded person and shows only their own project: no URL carries a project id, so there is nothing to guess (no IDOR)."""
import random

from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods, require_safe

from accounts.access import onboarded
from ledger import services as ledger
from ledger.rules import InsufficientCookies
from pages.live import live
from projects import conversation, notes, rules, script, services
from talk import flow
from talk.dialogue import fill

RNG = random.SystemRandom()      # the draw must not be predictable; tests swap in a seeded generator


@onboarded
@never_cache
def grandma(request):
    """The conversation. Someone with a project under way is sent to it instead of a second conversation."""
    cfg = live()
    steps = conversation.dialogue(cfg, request.user)
    store = conversation.Store(steps, cfg, RNG)
    if conversation.sent_away(request, store):
        return redirect("project")
    return flow.run(request, steps, store=store, finish=lambda request, answers: None, then=reverse("project"), title="Talk to Grandma")


@onboarded
@never_cache
@require_http_methods(["GET", "HEAD", "POST"])
def again(request):
    """Deal again. POST does it (free ones straight away; a paid one only after the confirmation page, which is this page's GET);
    a POST whose number is not the next re-deal's is a double click or an old page and changes nothing."""
    cfg = live()
    project = services.dealing_project(request.user)
    if project is None:
        return redirect("grandma")
    offer = rules.offer(project.redeals_used, cfg.REDEALS_FREE, cfg.REDEAL_COST)
    if request.method == "POST":
        if request.POST.get("expect") != str(offer.number):
            return redirect("grandma")                         # a double click or an old page: nothing happens
        if offer.cost and not request.POST.get("sure"):
            return redirect("grandma_again")                   # a paid one needs the confirmation first
        try:
            services.redeal(request.user, expect=offer.number, free=cfg.REDEALS_FREE, cost=cfg.REDEAL_COST, size=cfg.DEAL_SIZE, rng=RNG)
        except InsufficientCookies:
            return redirect("grandma_again")                   # that page says so in her voice
        return redirect("grandma")
    if not offer.cost:
        return redirect("grandma")
    return confirmation(request, offer)


def confirmation(request, offer):
    """Grandma asks "sure?", or says she is not giving credit."""
    balance = ledger.balance(request.user)
    affordable = balance >= offer.cost
    amounts = {"cost": conversation.cookies(offer.cost), "balance": conversation.cookies(balance)}
    lines = script.ASK_AGAIN if affordable else script.TOO_POOR
    return flow.page(request, title="Talk to Grandma", kind="again", face="sideeye" if affordable else "nose-up", then=reverse("grandma"),
                     lines=[fill(line, amounts) for line in lines],
                     again={"url": reverse("grandma_again"), "number": offer.number, "affordable": affordable})


@onboarded
@never_cache
@require_safe
def project(request):
    """The person's own project: the one in progress, else their latest. Nobody has anything to show before they have talked to
    Grandma, and a hand that is still on the table goes back to the conversation."""
    mine = services.active_project(request.user) or services.latest_project(request.user)
    if mine is None or mine.status == rules.DEALING:
        return redirect("grandma")
    request.session.pop("talk:grandma", None)          # the send-off has been seen
    cfg = live()
    window = rules.window(mine.started_at, timezone.now(), cfg.PROJECT_MIN_DAYS, cfg.PROJECT_MAX_DAYS) if mine.status == rules.BUILDING else None
    return render(request, "pages/project.html", {
        "project": mine, "status": rules.LABELS[mine.status], "window": window, "max_days": max(cfg.PROJECT_MIN_DAYS, cfg.PROJECT_MAX_DAYS),
        "min_days": cfg.PROJECT_MIN_DAYS, "notes": notes.notes(services.kept_demands(mine)), "can_start_another": not mine.active})
