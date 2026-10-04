"""The public pages: a person (/u/), a project (/p/), the Blue Ribbon wall (/ribbons/) and the cookie board (/leaderboard/). No login,
GET and HEAD only, and the same page for everyone: nothing here looks at who is asking. Templates get showcase/public.py's records only."""
from django.http import Http404, HttpResponsePermanentRedirect
from django.shortcuts import render
from django.views.decorators.http import require_safe

from pages.live import live
from showcase import public

NOINDEX = "noindex, nofollow"


def show(request, template, cfg, **context):
    """Render a public page. Unless the PUBLIC_PAGES_INDEXABLE setting is on, the page tells search engines to leave it alone, in a
    meta tag (the template) and in a header (this); the page itself stays open to anyone with the link."""
    response = render(request, template, {"indexable": cfg.PUBLIC_PAGES_INDEXABLE, **context})
    if not cfg.PUBLIC_PAGES_INDEXABLE:
        response.headers["X-Robots-Tag"] = NOINDEX
    return response


def canonical(request, page):
    """Nothing, or a 301 to the address the server computes from the name. The target is that path and nothing the visitor typed."""
    return None if request.path == page.path else HttpResponsePermanentRedirect(page.path)


@require_safe
def profile(request, pk, slug=None):
    cfg = live()
    page = public.profile_page(pk, request.GET.get("page"), cfg)
    if page is None:
        raise Http404
    return canonical(request, page) or show(request, "pages/public_profile.html", cfg, page=page)


@require_safe
def project(request, pk, slug=None):
    cfg = live()
    page = public.project_page(pk, cfg)
    if page is None:
        raise Http404
    return canonical(request, page) or show(request, "pages/public_project.html", cfg, page=page, share_url=request.build_absolute_uri(page.path))


@require_safe
def ribbons(request):
    cfg = live()
    return show(request, "pages/public_ribbons.html", cfg, wall=public.wall_page(request.GET.get("page"), cfg))


@require_safe
def leaderboard(request):
    cfg = live()
    return show(request, "pages/public_board.html", cfg, rows=public.board(cfg))
