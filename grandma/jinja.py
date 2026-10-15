"""Jinja2 environment for the site templates (the first backend in settings.TEMPLATES).

Same settings the Flask app had, plus the Django helpers templates need: static() and url(), and pantry_peek() and ribbon_wall_peek() for the home page
(this project package sits above every app, so it may wire `shop` and `showcase` in; `pages` stays below them and only passes the counts, pages/context.py).
`static()` adds `?v=<content hash>` so pages/static_cache.py can cache a file for a year; `art_src()` serves a picture's lossless `.webp` twin when one exists (tools/optimize_images.py).
`tojson` is built into Jinja2 and already escapes < > & ' for use inside a <script> tag.
"""
import hashlib
from functools import cache
from pathlib import Path

from django.conf import settings
from django.contrib.staticfiles import finders
from django.templatetags.static import static
from django.urls import reverse
from jinja2 import Environment

from shop.peek import pick as pantry_peek
from showcase.peek import pick as ribbon_wall_peek


@cache
def digest(path, mtime):
    """10 hex characters of the file's content hash. `mtime` only keys the cache: with DEBUG on, an edited file gets a new one at once."""
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()[:10]


def versioned_static(name):
    """The static URL with `?v=<hash of the file>`: a changed file is a new address, an unchanged one is cached for a year. A file that is not found keeps the plain URL."""
    url = static(name)
    path = finders.find(name)
    if not path:
        return url
    return f"{url}?v={digest(path, Path(path).stat().st_mtime_ns if settings.DEBUG else 0)}"


def art_src(name):
    """The URL of a picture in static/assets: the `.webp` twin of a PNG when it exists next to it, else the file itself (the PNGs stay as the fallback).
    A ready address (an uploaded picture, `/media/...` or a full URL, see shop/models.py `art_source`) is returned as it is."""
    if name.startswith(("/", "https://")):
        return name
    if name.endswith(".png") and finders.find(f"assets/{name[:-4]}.webp"):
        name = f"{name[:-4]}.webp"
    return versioned_static(f"assets/{name}")


def environment(**options):
    env = Environment(trim_blocks=True, lstrip_blocks=True, **options)
    env.globals.update(static=versioned_static, art_src=art_src, url=reverse, pantry_peek=pantry_peek, ribbon_wall_peek=ribbon_wall_peek)   # the home page's two peeks, see templates/pages/home.html
    return env
