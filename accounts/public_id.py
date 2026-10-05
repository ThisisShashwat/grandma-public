"""The random id in the public address of a person or a project (/u/<id>-<slug>/, /p/<id>-<slug>/), so the sequential database number
never shows and nobody can walk the pages by counting. 10 lowercase letters and digits is about 51 bits, made by Django's own
get_random_string (the secrets module). It sits here, under both models, because both use it as a field default."""
from django.utils.crypto import get_random_string

ALPHABET = "abcdefghijklmnopqrstuvwxyz0123456789"
LENGTH = 10
PATTERN = f"[a-z0-9]{{{LENGTH}}}"       # what a public id looks like in an address (showcase/urls.py)


def new_public_id():
    return get_random_string(LENGTH, ALPHABET)
