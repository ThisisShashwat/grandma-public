"""Before a page that matters (submissions/handover.py PAGES), send a person with a result waiting at Grandma's to her. A middleware
rather than a decorator on each view: the dashboard, the project page and Talk to Grandma live in other apps that must not know
about submissions, and the list of pages is in one place."""
from django.shortcuts import redirect

from submissions import handover, services


class CollectFirst:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        return self.get_response(request)

    def process_view(self, request, view_func, view_args, view_kwargs):
        match = request.resolver_match
        if match and match.url_name in handover.PAGES and request.user.is_authenticated and services.waiting(request.user):
            return redirect("collect")
