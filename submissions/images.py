"""The screenshot a person uploads, made safe before it is stored. Nothing about the file is trusted: not its name, its type or
its size. Pillow has to decode it as a PNG, JPEG or WebP of sane dimensions, and what is stored is a NEW image built from the
decoded pixels alone, so EXIF (camera, GPS position), comments, text chunks, colour profiles and anything hidden in the file
are gone. The file gets a random name made here. Privacy matters: the people are 13 to 18 and their photos carry locations."""
import io
import uuid

from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from PIL import Image, ImageOps

FORMATS = {"PNG": ("png", {}), "JPEG": ("jpg", {"quality": 90}), "WEBP": ("webp", {"quality": 90})}
MAX_SIDE = 6000              # pixels, width or height
MAX_PIXELS = 20_000_000      # width times height: what the decoder may be asked to hold in memory

NOT_A_PICTURE = "That isn't a picture I can read, dear. A PNG, JPEG or WebP, please."
TOO_BIG_PIXELS = f"That picture is enormous, dear. No side longer than {MAX_SIDE} pixels, please."


def too_big_file(max_bytes):
    return f"That file is too big, dear. {max_bytes // (1024 * 1024)} MB at the very most."


def clean_screenshot(upload, max_bytes):
    """A ContentFile with a random name holding a re-encoded copy of the upload. ValidationError, in Grandma's voice, if the
    upload is too big, is not a PNG, JPEG or WebP that Pillow can decode, or has too many pixels."""
    if upload.size > max_bytes:
        raise ValidationError(too_big_file(max_bytes))
    try:
        upload.seek(0)
        picture = Image.open(upload)
        kind = picture.format
        if kind not in FORMATS:
            raise ValidationError(NOT_A_PICTURE)
        width, height = picture.size
        if max(width, height) > MAX_SIDE or width * height > MAX_PIXELS:
            raise ValidationError(TOO_BIG_PIXELS)
        picture.load()                                  # decode every pixel now: a truncated or damaged file fails here
        return reencode(picture, kind)
    except ValidationError:
        raise
    except (OSError, ValueError, SyntaxError, MemoryError, Image.DecompressionBombError):
        raise ValidationError(NOT_A_PICTURE) from None


def reencode(picture, kind):
    """A fresh image of the same format that carries the pixels and nothing else."""
    upright = ImageOps.exif_transpose(picture)         # honour the camera's rotation before the EXIF that says so is dropped
    see_through = upright.mode in ("RGBA", "LA", "PA") or "transparency" in upright.info
    mode = "RGBA" if see_through and kind != "JPEG" else "RGB"
    pixels = upright.convert(mode)
    fresh = Image.new(mode, pixels.size)
    fresh.paste(pixels)                                 # a new image has an empty .info: no metadata can come along
    out = io.BytesIO()
    extension, options = FORMATS[kind]
    fresh.save(out, kind, **options)
    return ContentFile(out.getvalue(), name=f"{uuid.uuid4().hex}.{extension}")
