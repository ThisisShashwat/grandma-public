from django.shortcuts import render
from django.views.decorators.http import require_safe

from . import catalog


@require_safe
def shop(request):
    return render(request, "pages/shop.html", {"shop": catalog.build()})
