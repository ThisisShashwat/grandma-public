"""The screenshot a person uploads, made safe before it is stored. Nothing about the file is trusted: not its name, its type or
its size. Pillow has to decode it as a PNG, JPEG or WebP of sane dimensions, and what is stored is a NEW image built from the
decoded pixels alone, so EXIF (camera, GPS position), comments, text chunks, colour profiles and anything hidden in the file
are gone. The picture is also shrunk (never enlarged) to a storable size, see shrink. The file gets a random name made here. Privacy matters: the people are 13 to 18 and their photos carry locations."""
import io
import uuid
from contextlib import contextmanager, suppress

from django.core.cache import caches
from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from PIL import Image, ImageOps

FORMATS = {"PNG": ("png", {"optimize": True}), "JPEG": ("jpg", {"quality": 85, "optimize": True}), "WEBP": ("webp", {"quality": 85})}
MAX_SIDE = 6000              # pixels, width or height
MAX_PIXELS = 10_000_000      # width times height: what the decoder may be asked to hold in memory (10 and not 8: a 4K monitor screenshot is 8.3 million)
STORED_SIDE = 2000           # a stored picture is shrunk until its long side is at most this ...
STORED_PIXELS = 4_000_000    # ... and its width times height at most this, whichever shrinks more
DECODE_LOCK_SECONDS = 30     # how long a person's decode lock lives if nothing releases it

NOT_A_PICTURE = "That isn't a picture I can read, dear. A PNG, JPEG or WebP, please."
ONE_AT_A_TIME = "One picture at a time, dear. Wait for the first one to finish and try again."


def too_big_pixels(max_side=MAX_SIDE):
    return f"That picture is enormous, dear. No side longer than {max_side} pixels, please."


def too_big_file(max_bytes):
    return f"That file is too big, dear. {max_bytes // (1024 * 1024)} MB at the very most."


@contextmanager
def one_at_a_time(user_id):
    """Around a decode (the costly part): one at a time per person, so a script cannot make the server decode a pile of pictures at once.
    A second decode for the same person while the first holds the lock is a ValidationError; the lock is always given back, and expires by itself
    after DECODE_LOCK_SECONDS. It lives in the shared cache (the same store as the request limits, pages/rate_limit.py). If that store is down the
    work goes on without a lock: a limit must never be what takes the site down."""
    cache, key = caches["ratelimit"], f"decode:{user_id}"
    try:
        held = cache.add(key, 1, DECODE_LOCK_SECONDS)
    except Exception:
        held = None
    if held is False:
        raise ValidationError(ONE_AT_A_TIME)
    try:
        yield
    finally:
        if held:
            with suppress(Exception):
                cache.delete(key)


def clean_screenshot(upload, max_bytes, max_side=MAX_SIDE, max_pixels=MAX_PIXELS, side=STORED_SIDE):
    """A ContentFile with a random name holding a re-encoded copy of the upload. ValidationError, in Grandma's voice, if the
    upload is too big, is not a PNG, JPEG or WebP that Pillow can decode, or has too many pixels. The caps default to the limits
    above; the order proofs pass their admin settings (docs/orders.md), and the shop item art asks for a smaller stored `side` (shop/art.py)."""
    if upload.size > max_bytes:
        raise ValidationError(too_big_file(max_bytes))
    try:
        upload.seek(0)
        picture = Image.open(upload)
        kind = picture.format
        if kind not in FORMATS:
            raise ValidationError(NOT_A_PICTURE)
        width, height = picture.size
        if max(width, height) > max_side or width * height > max_pixels:
            raise ValidationError(too_big_pixels(max_side))
        picture.load()                                  # decode every pixel now: a truncated or damaged file fails here
        return reencode(picture, kind, side)
    except ValidationError:
        raise
    except (OSError, ValueError, SyntaxError, MemoryError, Image.DecompressionBombError):
        raise ValidationError(NOT_A_PICTURE) from None


def shrink(pixels, side=STORED_SIDE):
    """The same picture, never enlarged and in the same proportions, small enough to store: long side at most `side` (STORED_SIDE, 2000) and
    width times height at most STORED_PIXELS (4 million; a very tall page is shrunk by whichever limit bites harder, a 1280 by 4000 shot becomes 640 by 2000). Expects an RGB or RGBA image (a palette image would be resized without smoothing)."""
    width, height = pixels.size
    scale = min(1, side / max(width, height), (STORED_PIXELS / (width * height)) ** 0.5)
    if scale == 1:
        return pixels
    return pixels.resize((max(1, int(width * scale)), max(1, int(height * scale))), Image.LANCZOS)


def reencode(picture, kind, side=STORED_SIDE):
    """A fresh, downscaled (see shrink, to `side`) image of the same format that carries the pixels and nothing else."""
    upright = ImageOps.exif_transpose(picture)         # honour the camera's rotation before the EXIF that says so is dropped
    see_through = upright.mode in ("RGBA", "LA", "PA") or "transparency" in upright.info
    mode = "RGBA" if see_through and kind != "JPEG" else "RGB"
    pixels = shrink(upright.convert(mode), side)
    fresh = Image.new(mode, pixels.size)
    fresh.paste(pixels)                                 # a new image has an empty .info: no metadata can come along
    out = io.BytesIO()
    extension, options = FORMATS[kind]
    fresh.save(out, kind, **options)
    return ContentFile(out.getvalue(), name=f"{uuid.uuid4().hex}.{extension}")
