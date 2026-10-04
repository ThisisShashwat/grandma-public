"""Checking Hackatime hours from the submit note (docs/submissions.md): "Check my hours" or "Pick projects" goes to /hackatime/check/,
where the person picks their Hackatime projects. The stored encrypted token reads project lists and total seconds server side.
When Hackatime rejects the token, the person is redirected to connect again.
The numbers and names are kept on the project (services.record_hours) for services.submit to copy onto the submission.
Written DISABLED with the rest of Hackatime: 404 until HACKATIME_ENABLED is on and credentials and token keys are present."""
import logging
from urllib.parse import urlencode

from django.core.exceptions import ValidationError
from django.http import Http404
from django.shortcuts import redirect, render, resolve_url
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods

from accounts import hackatime
from accounts.access import onboarded
from accounts.services import profile_of
from pages.live import live
from program import duration
from projects import rules as project_rules
from submissions import services
from submissions.script import HOURS_NOT_ENOUGH, HOURS_REFUSALS

log = logging.getLogger(__name__)
STATUS = {"bad_name": 400, "failed": 400, "taken": 403}


def note_url(project):
    """The submit note this project is handed in on."""
    return resolve_url("submit") if project.status == project_rules.BUILDING else resolve_url("submit_fix", pk=project.pk)


def note_block(cfg, user, project):
    """What the submit note's Hackatime block shows, or None while Hackatime is switched off (the note then keeps its old greyed-out hint). Never a
    raw seconds number: only whether a check was made, names, count and time in words."""
    if not hackatime.enabled(cfg):
        return None
    checked = project.tracked_seconds is not None
    names = list(project.tracked_names)
    is_building = project.status == project_rules.BUILDING
    check_url = reverse("hackatime_check") if is_building else f"{reverse('hackatime_check')}?project={project.pk}"
    return {
        "connected": profile_of(user).hackatime_connected,
        "names": names,
        "checked": checked,
        "found": bool(project.tracked_seconds),
        "time": duration.text(project.tracked_seconds) if checked else "",
        "count": len(names),
        "required": hackatime.required(cfg),
        "check_url": check_url,
        "project": "" if is_building else project.pk,
    }


def require_fresh(cfg, project, now=None):
    """Before a hand-in: while hours are required, a check that found some must also be enough (hackatime.check_counts: long enough, newer than the
    project's start or last hand-in, and recent), or ValidationError. No check, or one that found nothing, is left for services.submit to refuse."""
    if not hackatime.required(cfg) or not project.tracked_seconds:
        return
    last = services.latest_round(project)
    if not hackatime.check_counts(project.tracked_seconds, project.tracked_at, last.submitted_at if last else project.started_at, now or timezone.now()):
        raise ValidationError(HOURS_NOT_ENOUGH)


def refused(request, reason, back):
    """Grandma's page for a check that did not go through, with the way back to the note."""
    label, line = HOURS_REFUSALS[reason]
    return render(request, "pages/hackclub_refused.html", {"label": label, "line": line, "back_url": back, "back_label": "Back to my note"}, status=STATUS[reason])


def to_check(user, wanted):
    """The project a check is for: the one being built (when wanted is empty), or the person's own project with changes requested (digits only, at most 9 chars)."""
    if not wanted:
        return services.shipping_project(user)
    if isinstance(wanted, str) and wanted.isascii() and wanted.isdigit() and len(wanted) <= 9:
        return services.fixing_project(user, int(wanted))
    return None


def connect_redirect(request, project=None):
    """Redirect to the connect flow with a safe next returning to this page."""
    path = request.get_full_path()
    if project and project.status != project_rules.BUILDING and "project=" not in path:
        sep = "&" if "?" in path else "?"
        path = f"{path}{sep}{urlencode({'project': project.pk})}"
    return redirect(f"{resolve_url('connect_hackatime')}?{urlencode({'next': path})}")


@onboarded
@never_cache
@require_http_methods(["GET", "POST"])
def check(request):
    """Pick Hackatime projects and count their hours using the stored token.
    GET: renders the picker with listed projects and times.
    POST: validates chosen names and records hours from Hackatime."""
    if not hackatime.enabled(live()):
        raise Http404

    profile = profile_of(request.user)
    if not profile.hackatime_connected:
        return connect_redirect(request)

    if request.method == "GET":
        project = to_check(request.user, request.GET.get("project", ""))
        if project is None:
            raise Http404

        now = timezone.now()
        start, end = hackatime.window(project, now)
        try:
            listed = hackatime.list_projects(profile, start, end)
        except hackatime.Reconnect:
            return connect_redirect(request, project)
        except hackatime.Unreadable:
            log.warning("hackatime check failed")
            return refused(request, "failed", note_url(project))

        tracked_set = set(project.tracked_names)
        rows = []
        listed_names = set()
        for name, seconds in listed:
            listed_names.add(name)
            rows.append({
                "name": name,
                "time": duration.text(seconds),
                "ticked": name in tracked_set,
            })
        for name in project.tracked_names:
            if name not in listed_names:
                rows.append({
                    "name": name,
                    "time": duration.text(0),
                    "ticked": True,
                })

        context = {
            "project_name": project.name,
            "rows": rows,
            "action": request.get_full_path(),
            "back_url": note_url(project),
            "project_id": "" if project.status == project_rules.BUILDING else project.pk,
        }
        return render(request, "pages/hackatime_pick.html", context)

    # POST
    project = to_check(request.user, request.POST.get("project", ""))
    if project is None:
        raise Http404

    back = note_url(project)
    names = request.POST.getlist("names")

    if not (1 <= len(names) <= hackatime.MAX_PROJECTS) or len(set(names)) != len(names):
        return refused(request, "bad_name", back)
    if not all(hackatime.clean_name(name) == name for name in names):
        return refused(request, "bad_name", back)

    now = timezone.now()
    start, end = hackatime.window(project, now)
    try:
        seconds = hackatime.total_seconds(profile, names, start, end)
    except hackatime.Reconnect:
        return connect_redirect(request, project)
    except (hackatime.Unreadable, ValueError):
        log.warning("hackatime check failed")
        return refused(request, "failed", back)

    try:
        recorded = services.record_hours(request.user, project.pk, names, seconds)
    except services.NameTaken:
        return refused(request, "taken", back)

    if recorded is None:
        log.warning("hackatime check failed")
        return refused(request, "failed", back)

    return redirect(back)
