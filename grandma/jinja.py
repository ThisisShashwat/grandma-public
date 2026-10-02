"""Jinja2 environment for the site templates (the first backend in settings.TEMPLATES).

Same settings the Flask app had, plus the two Django helpers templates need: static() and url().
`tojson` is built into Jinja2 and already escapes < > & ' for use inside a <script> tag.
"""
from django.templatetags.static import static
from django.urls import reverse
from jinja2 import Environment


def environment(**options):
    env = Environment(trim_blocks=True, lstrip_blocks=True, **options)
    env.globals.update(static=static, url=reverse)
    return env
