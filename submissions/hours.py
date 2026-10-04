"""Checking Hackatime hours from the submit note (docs/submissions.md): "Check my hours" posts the name of a Hackatime project to /hackatime/check/, which
keeps it (and the project, and when it started) in the session and sends the person to Hackatime; /hackatime/check/callback/ is where Hackatime sends
them back. There accounts/hackatime.py reads the seconds of that project since the project started, and revokes the token; the seconds are kept on the
project (services.record_hours) for services.submit to copy onto the submission. The number is for reviewers: no page here or on the note shows it.
Written DISABLED with the rest of Hackatime: 404 until HACKATIME_ENABLED is on and the person has connected their account."""
import logging
from datetime import datetime

from django.http import Http404, HttpResponseNotAllowed
from django.shortcuts import redirect, render, resolve_url
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET

from accounts import hackatime
from accounts.access import onboarded
from accounts.services import profile_of
from pages.live import live
from projects import rules as project_rules
from submissions import services
from submissions.script import HOURS_REFUSALS

log = logging.getLogger(__name__)
CHECK = "hackatime_check"          # the session key that carries the name, the project and the start of the window over to the callback
STATUS = {"bad_name": 400, "failed": 400, "taken": 403}


def note_url(project):
    """The submit note this project is handed in on."""
    return resolve_url("submit") if project.status == project_rules.BUILDING else resolve_url("submit_fix", pk=project.pk)


def note_block(cfg, user, project):
    """What the submit note's Hackatime block shows, or None while Hackatime is switched off (the note then keeps its old greyed-out hint). Never a
    number: only whether a check was made and whether it found any time."""
    if not hackatime.enabled(cfg):
        return None
    return {"connected": profile_of(user).hackatime_connected, "name": project.tracked_name, "checked": project.tracked_seconds is not None,
            "found": bool(project.tracked_seconds), "required": hackatime.required(cfg),
            "project": "" if project.status == project_rules.BUILDING else project.pk}


def refused(request, reason, back):
    """Grandma's page for a check that did not go through, with the way back to the note."""
    label, line = HOURS_REFUSALS[reason]
    return render(request, "pages/hackclub_refused.html", {"label": label, "line": line, "back_url": back, "back_label": "Back to my note"}, status=STATUS[reason])


def to_check(request):
    """The project a posted check is for: the one being built, or (the fix page posts its id) the person's own project with changes requested."""
    wanted = request.POST.get("project", "")
    if not wanted:
        return services.shipping_project(request.user)
    return services.fixing_project(request.user, int(wanted)) if wanted.isdigit() and len(wanted) <= 9 else None


@onboarded
@never_cache
def check(request):
    """Sends the person to Hackatime to have the hours of one project counted. POST only, with the CSRF token. 404 until Hackatime is switched on, for a
    person who has not connected, and for a project that is not their own and ready to hand in. Only the name, the project and when it started are
    kept (in the session) before leaving."""
    profile = profile_of(request.user)
    if not (hackatime.enabled(live()) and profile.hackatime_connected):
        raise Http404
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])
    project = to_check(request)
    if project is None:
        raise Http404
    name = hackatime.clean_name(request.POST.get("name", ""))
    if name is None:
        return refused(request, "bad_name", note_url(project))
    request.session[CHECK] = {"name": name, "project": project.pk, "start": project.started_at.isoformat()}
    try:
        return hackatime.authorize_redirect(request, "hackatime_check_callback")
    except Exception:
        log.warning("hackatime check failed")
        return refused(request, "failed", note_url(project))


def window_of(pending):
    """(name, project id, start) from what `check` kept in the session, or None when the session has nothing, or not that."""
    try:
        name, project_id, start = pending["name"], int(pending["project"]), datetime.fromisoformat(pending["start"])
    except (KeyError, TypeError, ValueError):
        return None
    return (name, project_id, start) if hackatime.clean_name(name) == name else None


@onboarded
@never_cache
@require_GET
def check_callback(request):
    """Where Hackatime sends the person back. The library checks the state and the code; we read the seconds of the project from its start until now, check
    it is the account they connected, and revoke the token at once (accounts/hackatime.py). Then the number is kept on the project, refused when the name
    already backs another of theirs. Nothing is taken from this request, and no token is kept."""
    profile = profile_of(request.user)
    if not (hackatime.enabled(live()) and profile.hackatime_connected):
        raise Http404
    back = resolve_url("submit")
    window = window_of(request.session.pop(CHECK, None))
    if window is None:
        log.warning("hackatime check failed")
        return refused(request, "failed", back)
    name, project_id, start = window
    seconds = hackatime.seconds_of(request, profile.hackatime_user_id, name, start, timezone.now())
    if seconds is None:
        log.warning("hackatime check failed")
        return refused(request, "failed", back)
    try:
        project = services.record_hours(request.user, project_id, name, seconds)
    except services.NameTaken:
        return refused(request, "taken", back)
    if project is None:
        return refused(request, "failed", back)
    return redirect(note_url(project))
