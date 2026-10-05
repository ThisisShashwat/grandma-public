"""/submit/ (a person hands their building project to Grandma), /submit/<id>/ (they fix a project she asked changes of and hand it in
again) and /grandma/collect/ (she hands the result back). All are for one signed-in, onboarded person and touch only their own
project: the only id in an address is the project to fix, and it is only found among the person's own projects with changes requested."""
from functools import partial

from django.core.exceptions import ValidationError
from django.http import Http404, HttpResponseBadRequest
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods

from accounts import hackatime
from accounts.access import onboarded
from pages.live import live
from projects import rules as project_rules
from projects import services as project_services
from projects.models import Project
from submissions import handover, hours, script, services
from submissions.forms import SubmitForm
from talk import flow
from talk.dialogue import End
from talk.portraits import portrait

MAX_FILES = 3           # the note takes one screenshot; the site-wide limit is higher because an order carries more (settings.py)
STARTS_FROM = ("repo_url", "playable_url", "description", "recording_url", "ai_declaration_text")   # a fix starts from the last round's words


@onboarded
@never_cache
@require_http_methods(["GET", "HEAD", "POST"])
def submit(request, pk=None):
    """Grandma's note. Without an id only a project being built can be handed in; with none being built, the person's only project with
    changes requested sends them to its page, anything else gets her saying why. With the id of the person's own project that has
    changes requested, the next round of it, the form starting from the last round's words (one already with Grandma gets her saying so).
    A hand-in that works goes to the dashboard."""
    if sum(len(files) for _, files in request.FILES.lists()) > MAX_FILES:
        return HttpResponseBadRequest("Too many files.")
    cfg = live()
    project = services.shipping_project(request.user) if pk is None else services.fixing_project(request.user, pk)
    if project is None:
        if pk is not None:
            return just_handed_in(request, pk)
        sole = services.sole_fixing_project(request.user)
        return redirect("submit_fix", pk=sole.pk) if sole else not_now(request)
    ship = services.ship_for(project)
    if ship.problem:
        return not_now(request, ship.problem) if pk is None else turned_back(request, ship.problem)
    hours_rules = {"hackatime_required": hackatime.required(cfg), "hours_check": partial(hours.require_fresh, cfg)}
    if request.method == "POST":
        form = SubmitForm(request.POST, request.FILES, cfg=cfg, precheck=partial(services.check_hours, project, **hours_rules))
    else:
        form = SubmitForm(cfg=cfg, initial=starts_from(project) if pk else None)
    if request.method == "POST" and form.is_valid():
        try:
            services.submit(request.user, project_id=pk, **hours_rules, **form.cleaned_data)
        except ValidationError as error:
            form.add_error(None, error)
        else:
            request.session["handed_in"] = True
            return redirect("dashboard")
    return render(request, "pages/submit.html", {
        "form": form, "checks": form.checks, "project_name": project.name, "action": request.path, "round": ship.number if pk else 0, "max_rounds": max(cfg.MAX_ROUNDS, ship.number),
        "portrait": dict(zip(("file", "alt"), portrait("sideeye" if form.errors else "writing"))), "max_mb": cfg.SCREENSHOT_MAX_MB, "sleepers": form.blocked_hosts[:3],
        "hackatime": hours.note_block(cfg, request.user, project)})


def starts_from(project):
    """The last round's description, links and AI text, as the form's starting values (the screenshot and the ticks are never carried over)."""
    last = services.latest_round(project)
    return {field: getattr(last, field) for field in STARTS_FROM} if last else None


def just_handed_in(request, pk):
    """The fix page of a project the person owns that is already with Grandma (a double click, a second tab): her saying so. Any other id, a
    404."""
    if not Project.objects.filter(pk=pk, user=request.user, status__in=(project_rules.IN_REVIEW, project_rules.SHIPPED)).exists():
        raise Http404
    return flow.page(request, title="Hand it in", kind="end", face="magnifier", then=reverse("dashboard"), lines=script.STILL_READING, step=End(button="To my dashboard"))


def turned_back(request, problem):
    """A project with changes requested that cannot be handed in again (no round left): Grandma says so."""
    return flow.page(request, title="Hand it in", kind="end", face="sideeye", then=reverse("dashboard"), lines=(problem,), step=End(button="To my dashboard"))


def not_now(request, problem=""):
    """Grandma says why there is nothing to hand in: no project yet, or it is already with her, or finished."""
    latest = project_services.latest_project(request.user)
    if latest is None or latest.status == project_rules.DEALING:
        return redirect("grandma")
    if problem:
        lines, face, then, button = (problem,), "sideeye", reverse("project"), "Back to my project"
    else:
        working = project_services.working_project(request.user)
        has_in_review = Project.objects.filter(user=request.user, status__in=(project_rules.IN_REVIEW, project_rules.SHIPPED)).exists()
        if working is None and (latest.status in (project_rules.IN_REVIEW, project_rules.SHIPPED) or has_in_review):
            lines, face, then, button = script.STILL_READING, "magnifier", reverse("grandma"), "Talk to Grandma about a new one"
        elif latest.status in (project_rules.IN_REVIEW, project_rules.SHIPPED):
            lines, face, then, button = script.STILL_READING, "magnifier", reverse("dashboard"), "To my dashboard"
        else:
            lines, face, then, button = script.NOTHING_TO_HAND_IN, "clipboard", reverse("grandma"), "Talk to Grandma"
    return flow.page(request, title="Hand it in", kind="end", face=face, then=then, lines=lines, step=End(button=button))


@onboarded
@never_cache
@require_http_methods(["GET", "HEAD", "POST"])
def collect(request):
    """Grandma reads the reviewer's note and hands over the cookies. Nothing waiting (and no send-off to show): back to the dashboard."""
    submission = handover.current(request)
    if submission is None:
        return redirect("dashboard")
    steps = handover.dialogue(live(), submission)
    return flow.run(request, steps, store=handover.Store(submission, steps), finish=lambda request, answers: None, then=handover.then(submission),
                    title="Grandma has something for you")
