"""Talk to Grandma (/grandma/, /grandma/again/), the person's project (/project/) and the complaints box (/complaints/). Every page here
is for one signed-in, onboarded person and shows only their own project: no URL carries a project id, so there is nothing to guess (no IDOR)."""
import random

from django.conf import settings
from django.core.exceptions import ValidationError
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods, require_safe

from accounts.access import onboarded
from ledger import services as ledger
from ledger.rules import InsufficientCookies
from pages.live import live
from projects import complaints as complaint_service
from projects import conversation, notes, rules, script, services
from projects.forms import ComplaintForm
from talk import flow
from talk.dialogue import fill
from talk.portraits import portrait

RNG = random.SystemRandom()      # the draw must not be predictable; tests swap in a seeded generator
PILE = ("grandma-complaints.png", "Grandma buried under a mountain of complaint notes")          # the complaints page: her under the notes


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
    if not services.can_redeal(project, cfg.DEAL_SIZE):
        return nothing_new(request)                            # no deal could differ (Other): never asked for, never charged
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
        except ValidationError:
            return nothing_new(request)                        # the same refusal, if the jar changed since the check above
        return redirect("grandma")
    if not offer.cost:
        return redirect("grandma")
    return confirmation(request, offer)


def nothing_new(request):
    """Grandma has no other hand for this kind of project: her say so, a way back, nothing charged or changed."""
    return flow.page(request, title="Talk to Grandma", kind="end", face=script.NOTHING_NEW.face, then=reverse("grandma"),
                     lines=[services.NOTHING_NEW], step=script.NOTHING_NEW)


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


#: A project in one of these has no public page yet (or any more). The rule is showcase/rules.py and showcase/public.py project_page: a page needs
#: a handed-in ship, and staff pull an abandoned project off. Copied here on purpose: nothing may import showcase.
NOT_PUBLIC = (rules.DEALING, rules.BUILDING, rules.ABANDONED)


def share_url(request, project):
    """The address of the project's public page, absolute, for the Share box; "" while the project has no public page. The bare route is
    used because the server redirects /p/<public id>/ to the canonical slug itself."""
    if project.status in NOT_PUBLIC:
        return ""
    return settings.SITE_URL.rstrip("/") + reverse("public_project_bare", kwargs={"public_id": project.public_id})


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
            "notes": notes.notes(services.kept_demands(shown)), "can_start_another": False, "share_url": share_url(request, shown)})
    else:
        context.update({
            "project": None, "can_start_another": True})
    return render(request, "pages/project.html", context)


@onboarded
@never_cache
@require_http_methods(["GET", "HEAD", "POST"])
def complaints(request):
    """Send Grandma a complaint, a suggestion for a new demand. POST then redirect, so a refresh never sends it twice; the redirect lands
    on the thank you, shown once. Nothing sent here is ever shown to anybody but staff."""
    form = ComplaintForm(request.POST) if request.method == "POST" else ComplaintForm()
    if request.method == "POST" and form.is_valid():
        try:
            complaint_service.send_complaint(request.user, **form.cleaned_data)
        except ValidationError as error:
            form.add_error(None, error)
        else:
            request.session["complaint_sent"] = True
            return redirect("complaints")
    sent = request.method == "GET" and request.session.pop("complaint_sent", False)
    file, alt = portrait("smug") if sent else portrait("sideeye") if form.errors else PILE
    return render(request, "pages/complaints.html", {"form": form, "sent": sent, "portrait": {"file": file, "alt": alt}})
