"""The one way code reads the settings staff edit in the admin (program/runtime.py, django-constance)."""
from types import SimpleNamespace

from constance.utils import get_values


def live():
    """Every admin-editable setting as attributes, in a single query: live().DEAL_SIZE. Anything nobody has saved is its
    default, so this works on a fresh database too. (constance's own `config.X` makes one query per read and writes
    the default back on the first read, which a page view should not do.)"""
    return SimpleNamespace(**get_values())
