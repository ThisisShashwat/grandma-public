"""Jinja2 environment for the site templates (the first backend in settings.TEMPLATES).

Same settings the Flask app had, plus the two Django helpers templates need: static() and url(), and pantry_peek() for the home page
(this project package sits above every app, so it may wire `shop` in; `pages` stays below `shop` and only passes the count, pages/context.py).
`tojson` is built into Jinja2 and already escapes < > & ' for use inside a <script> tag.
"""
from django.templatetags.static import static
from django.urls import reverse
from jinja2 import Environment

from shop.peek import pick as pantry_peek


def environment(**options):
    env = Environment(trim_blocks=True, lstrip_blocks=True, **options)
    env.globals.update(static=static, url=reverse, pantry_peek=pantry_peek)   # pantry_peek: the home page's few Pantry items, see templates/pages/home.html
    return env
