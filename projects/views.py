"""Talk to Grandma (/grandma/, /grandma/again/) and the person's project (/project/). Every page here is for one signed-in,
onboarded person and shows only their own project: no URL carries a project id, so there is nothing to guess (no IDOR)."""
import random

from django.shortcuts import redirect, render
from django.urls import reverse
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
    request.session.pop("talk:project_edit", None)
    request.session.pop("talk:project_demands", None)
    return flow.run(request, steps, store=store, finish=lambda request, answers: None, then=reverse("project"), title="Talk to Grandma")


@onboarded
@never_cache
@require_http_methods(["GET", "HEAD", "POST"])
def again(request):
    """Deal again. POST does it (free ones straight away; a paid one only after the confirmation page, which is this page's GET);
    a POST whose number is not the next re-deal's is a double click or an old page and changes nothing."""
    cfg = live()
    project = services.working_project(request.user)
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
def project_edit(request):
    """Edit the idea, name, category, or subcategory of a working project."""
    project = services.working_project(request.user)
    if project is None:
        return redirect("project")
    steps = conversation.edit_dialogue(project)
    store = conversation.EditStore(steps, project)
    then = reverse("grandma") if project.status == rules.DEALING else reverse("project")
    return flow.run(request, steps, store=store, finish=lambda request, answers: None, then=then, title="Talk to Grandma")


@onboarded
@never_cache
def project_demands(request):
    """Edit the kept demands of a building project."""
    working = services.working_project(request.user)
    if working is not None and working.status == rules.DEALING:
        return redirect("grandma")
    if working is None or working.status != rules.BUILDING:
        return redirect("project")
    cfg = live()
    steps = conversation.demands_dialogue(working, cfg)
    store = conversation.DemandsStore(steps, working)
    return flow.run(request, steps, store=store, finish=lambda request, answers: None, then=reverse("project"), title="Talk to Grandma")


def fixing(user):
    """The person's latest project when it has changes requested (nothing is being worked on), else None."""
    latest = services.latest_project(user)
    return latest if latest is not None and latest.status == rules.CHANGES_REQUESTED else None


@onboarded
@never_cache
@require_safe
def project(request):
    """The person's own project: the working project if they have one, else their latest if it has changes requested (with what to
    change), else an empty state when other projects exist. Nobody has anything to show before they have talked to Grandma, and a hand
    that is still on the table goes back to the conversation."""
    working = services.working_project(request.user)
    if working is not None and working.status == rules.DEALING:
        return redirect("grandma")
    others = services.other_projects(request.user, limit=30)
    if working is None and not others:
        return redirect("grandma")
    request.session.pop("talk:grandma", None)          # the send-off has been seen
    request.session.pop("talk:project_edit", None)
    request.session.pop("talk:project_demands", None)
    shown = working or fixing(request.user)
    context = {"others": [row for row in others if shown is None or row.id != shown.id]}
    if shown is not None:
        context.update({
            "project": shown, "status": rules.LABELS[shown.status], "change_note": services.change_note(shown) if shown.status == rules.CHANGES_REQUESTED else "",
            "notes": notes.notes(services.kept_demands(shown)), "can_start_another": False})
    else:
        context.update({
            "project": None, "can_start_another": True})
    return render(request, "pages/project.html", context)
