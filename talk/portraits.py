"""Which picture of Grandma a step shows. A step's `face` is one of her ten faces (program/content/faces.py) or one of the
poses below. Pure Python, no Django import."""
from program.content.faces import FACES

POSES = {
    "wave": ("grandma-wave.png", "Grandma waving hello"),
    "clipboard": ("grandma-clipboard.png", "Grandma holding a clipboard, waiting"),
    "writing": ("grandma-writing.png", "Grandma scribbling on a piece of paper"),
    "phone": ("grandma-phone.png", "Grandma on an old corded phone, mid-sentence"),
    "finger": ("grandma-finger.png", "Grandma raising one finger, about to make a point"),
    "wag": ("grandma-finger-wag.png", "Grandma wagging her finger"),
    "book": ("grandma-book.png", "Grandma reading a big book, doing her homework"),
    "magnifier": ("grandma-magnifier.png", "Grandma squinting through a magnifying glass"),
    "cookie-jar": ("grandma-cookie-jar.png", "Grandma hugging a jar full of cookies"),
    "note": ("grandma-note-pull.png", "Grandma holding up a note she pulled from the jar"),
    "ribbon": ("grandma-ribbon.png", "Grandma proudly wearing a blue ribbon"),
    "hug": ("grandma-hug.png", "Grandma with her arms wide open for a hug"),
    "shush": ("grandma-shush.png", "Grandma winking, a finger to her lips"),
    "nose-up": ("grandma-nose-up.png", "Grandma with her nose in the air and arms crossed"),
    "shocked": ("grandma-shocked.png", "Grandma shocked, a cookie falling out of her hand"),
}

_portraits = {f["name"]: (f["file"], f["alt"]) for f in FACES} | POSES


def portrait(name):
    """(file in static/assets, alt text) for a face or pose name. KeyError for a name that does not exist."""
    return _portraits[name]
