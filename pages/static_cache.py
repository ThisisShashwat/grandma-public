"""Static files are cached hard (docs/deployment.md "Static files and caching").

The templates' `static()` adds `?v=<content hash>` (grandma/jinja.py), so an address with a `v` always means the same bytes: a year, immutable.
Without it (a CSS `url()` or a JS module import cannot know the hash) one hour, so art replaced under the same file name shows within the hour.
It sits before WhiteNoise and replaces WhiteNoise's own header. Only a good answer is touched (a 404 must never be cached) and only STATIC_URL, never MEDIA_URL.
With a preview password the header says `private`, so a shared cache never keeps a file that was behind the password."""
from django.conf import settings

YEAR = "max-age=31536000, immutable"
HOUR = "max-age=3600"
GOOD = (200, 206, 304)


def static_cache(get_response):
    def middleware(request):
        response = get_response(request)
        if request.path.startswith(settings.STATIC_URL) and response.status_code in GOOD:
            response["Cache-Control"] = f"{'private' if settings.PREVIEW_PASSWORD else 'public'}, {YEAR if 'v' in request.GET else HOUR}"
        return response
    return middleware
