"""The host's health probes, answered before Django looks at the Host header. A Kubernetes style probe often sends the pod's own address as Host,
which ALLOWED_HOSTS rightly refuses with a 400 for every other page; /healthz and /readyz only say "ok" or "database unreachable", so they may answer
for any Host. Nothing else is touched. Sits after the preview gate and WhiteNoise (the gate keeps the probes open, pages/preview_gate.py)."""
from pages import views

PROBES = {"/healthz": views.healthz, "/readyz": views.readyz}


def probes(get_response):
    def middleware(request):
        view = PROBES.get(request.path_info) if request.method in ("GET", "HEAD") else None
        return view(request) if view else get_response(request)
    return middleware
