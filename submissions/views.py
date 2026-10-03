"""/submit/ (a person hands their project to Grandma) and /grandma/collect/ (she hands the result back). Both are for one signed-in,
onboarded person and touch only their own project: no address carries a project or submission id, so there is nothing to guess."""
from django.core.exceptions import ValidationError
from django.http import HttpResponseBadRequest
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods

from accounts.access import onboarded
from pages.live import live
from projects import rules as project_rules
from projects import services as project_services
from projects.models import Project
from submissions import handover, script, services
from submissions.forms import SubmitForm
from talk import flow
from talk.dialogue import End
from talk.portraits import portrait

MAX_FILES = 3           # the note takes one screenshot; the site-wide limit is higher because an order carries more (settings.py)


@onboarded
@never_cache
@require_http_methods(["GET", "HEAD", "POST"])
def submit(request):
    """Grandma's note. Only a project being built can be handed in; anything else gets her saying why.
    A hand-in that works goes to the dashboard."""
    if sum(len(files) for _, files in request.FILES.lists()) > MAX_FILES:
        return HttpResponseBadRequest("Too many files.")
    project = services.shipping_project(request.user)
    if project is None:
        return not_now(request)
    ship = services.ship_for(project)
    if ship.problem:
        return not_now(request, ship.problem)
    cfg = live()
    form = SubmitForm(request.POST, request.FILES, cfg=cfg) if request.method == "POST" else SubmitForm(cfg=cfg)
    if request.method == "POST" and form.is_valid():
        try:
            services.submit(request.user, **form.cleaned_data)
        except ValidationError as error:
            form.add_error(None, error)
        else:
            request.session["handed_in"] = True
            return redirect("dashboard")
    return render(request, "pages/submit.html", {
        "form": form, "checks": form.checks, "project_name": project.name,
        "portrait": dict(zip(("file", "alt"), portrait("sideeye" if form.errors else "writing"))), "max_mb": cfg.SCREENSHOT_MAX_MB, "sleepers": form.blocked_hosts[:3]})


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
    steps = handover.dialogue(submission)
    return flow.run(request, steps, store=handover.Store(submission, steps), finish=lambda request, answers: None, then=reverse("dashboard"),
                    title="Grandma has something for you")
