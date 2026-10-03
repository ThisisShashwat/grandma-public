from django.http import Http404
from django.shortcuts import render
from django.views.decorators.http import require_safe

from . import loader, widgets


@require_safe
def index(request):
    return render(request, "pages/guides.html", {"sections": loader.sections(loader.all_guides())})


@require_safe
def page(request, slug):
    guides = loader.all_guides()
    guide = loader.get(slug)
    if guide is None:
        raise Http404
    previous, following = loader.neighbours(guides, slug)
    return render(request, "pages/guide.html", {
        "guide": guide, "body": widgets.expand(guide.html), "sections": loader.sections(guides),
        "previous": previous, "following": following,
    })
