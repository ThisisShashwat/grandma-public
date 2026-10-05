"""The preview gate: an optional HTTP Basic password in front of the WHOLE site, for a private preview (docs/security.md "Private preview").

With `settings.PREVIEW_PASSWORD` empty (the default) nothing happens. With it set, every request (static files, media, the admin, the Hack Club callback,
everything) needs the password in an `Authorization: Basic` header (the user name is ignored), or it gets a plain 401, and every response carries
`X-Robots-Tag: noindex`. The password is never logged and never put in a response."""
import base64
import hmac

from django.conf import settings
from django.http import HttpResponse

NOINDEX = "noindex, nofollow, noarchive"
CHALLENGE = 'Basic realm="Grandma preview", charset="UTF-8"'


def given_password(request):
    """The password of an `Authorization: Basic` header as bytes, or None when the header is missing or malformed."""
    scheme, _, token = request.headers.get("Authorization", "").partition(" ")
    if scheme.lower() != "basic":
        return None
    try:
        return base64.b64decode(token.strip(), validate=True).partition(b":")[2]
    except ValueError:      # not base64 (binascii.Error), or not ASCII
        return None


def refused():
    return HttpResponse("Grandma is not receiving visitors.", status=401, content_type="text/plain; charset=utf-8", headers={"WWW-Authenticate": CHALLENGE})


def preview_gate(get_response):
    def middleware(request):
        if not settings.PREVIEW_PASSWORD:
            return get_response(request)
        given = given_password(request)
        response = get_response(request) if given is not None and hmac.compare_digest(given, settings.PREVIEW_PASSWORD.encode()) else refused()
        response["X-Robots-Tag"] = NOINDEX
        return response
    return middleware
