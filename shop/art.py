"""The picture staff upload for a shop item (the "upload art" box in the admin). Nothing about the file is trusted: it is made safe like a screenshot
(submissions/images.py: decoded, rebuilt from its pixels alone, no metadata, a random name) and shrunk to what a card can show, so a big photo never slows the Pantry."""
from submissions import images

MAX_BYTES = 3 * 1024 * 1024
SIDE = 800                 # pixels, the longest side of the stored picture (a card shows it far smaller)


def clean(upload):
    """A ContentFile with a random name, or a ValidationError in Grandma's voice (too big, not a PNG, JPEG or WebP, too many pixels)."""
    return images.clean_screenshot(upload, MAX_BYTES, max_side=4000, max_pixels=12_000_000, side=SIDE)
