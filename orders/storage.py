"""Where order proofs (cart and part screenshots) are kept: PRIVATE_MEDIA_ROOT, outside static and outside the public MEDIA_ROOT, and
with no web address at all. The only way to a file is the login-checked view in orders/views.py. Names are random and made here,
whatever the file was called. The folder must never be served by the web server (docs/orders.md)."""
import os
import uuid
from pathlib import Path

from django.conf import settings
from django.core.files.storage import FileSystemStorage

from submissions.images import FORMATS

EXTENSIONS = {f".{extension}" for extension, _ in FORMATS.values()}


class PrivateStorage(FileSystemStorage):
    """A file system storage rooted at settings.PRIVATE_MEDIA_ROOT (read every time, so tests can move it) that cannot make a URL. Files are
    readable by the site's own user only (0o600, folders 0o700): the web server must not read them, only the login-checked view does."""

    file_permissions_mode = 0o600
    directory_permissions_mode = 0o700

    @property
    def base_location(self):
        return settings.PRIVATE_MEDIA_ROOT

    @property
    def location(self):
        return os.path.abspath(self.base_location)

    def url(self, name):
        raise ValueError("Order proofs are private: they have no web address, only the login-checked view.")


def private_storage():
    """The storage the proof fields use (a callable, so a migration can name it)."""
    return PrivateStorage()


def proof_path(instance, filename):
    """Always a random name under proofs/: the file's own name is never used (images.py already made a random one)."""
    extension = Path(filename).suffix.lower()
    return f"proofs/{uuid.uuid4().hex}{extension if extension in EXTENSIONS else '.png'}"
