from django.http import Http404
from django.shortcuts import redirect, render
from django.views.decorators.http import require_safe

from pages.context import program_links
from pages.live import live
from pages.public_cache import public_cache

from . import loader, widgets


@require_safe
def index(request):
    """There is no list of all guides: Guides opens the first page (Start here), the sidebar has the rest."""
    return redirect("guide", slug=loader.all_guides()[0].slug)


@require_safe
@public_cache
def page(request, slug):
    guides = loader.all_guides()
    guide = loader.get(slug)
    if guide is None:
        raise Http404
    previous, following = loader.neighbours(guides, slug)
    return render(request, "pages/guide.html", {
        "guide": guide, "body": widgets.expand(guide.html, program_links(live())), "sections": loader.sections(guides),
        "previous": previous, "following": following,
    })
