from django.http import HttpResponseNotAllowed

from pages.views import error_page


def method_not_allowed_page(get_response):
    """A wrong method comes back from a view as a plain 405 response, not an exception, so Django has no handler for it: dress
    the empty one in Grandma's page and keep its Allow header."""
    def middleware(request):
        response = get_response(request)
        if isinstance(response, HttpResponseNotAllowed) and not response.content:
            page = error_page(request, "405")
            page["Allow"] = response["Allow"]
            return page
        return response
    return middleware
