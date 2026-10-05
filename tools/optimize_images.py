"""Lossless WebP copies of the art in static/assets. Run by hand: `python tools/optimize_images.py [folder]`.

Next to every PNG it writes `<name>.webp` (lossless, alpha kept), after decoding the WebP and checking every RGBA pixel against the PNG.
A WebP that is not smaller than its PNG is not written. For art shown at one fixed CSS size (FIXED) it also writes `<name>-2x.webp`
at exactly twice that size (LANCZOS, so a different resolution, for sharp screens). Never overwrites or deletes: a file that exists is skipped,
the PNGs stay as the fallback (grandma/jinja.py `art_src` picks the WebP only when it exists). Prints a before and after table."""
import io
import sys
from pathlib import Path

from PIL import Image

ASSETS = Path(__file__).resolve().parent.parent / "static" / "assets"
FIXED = {"logo-mark": (56, 56)}      # name: the size it is shown at (templates/components/header.html)


def rgba(image):
    return image.convert("RGBA").tobytes()


def encode(image):
    """Lossless WebP bytes that decode to exactly the image's pixels, or None."""
    for exact in (False, True):      # exact also keeps the colour under fully transparent pixels, which the first try may drop (invisible, but not equal)
        buffer = io.BytesIO()
        image.save(buffer, "WEBP", lossless=True, method=6, exact=exact)
        if rgba(Image.open(io.BytesIO(buffer.getvalue()))) == rgba(image):
            return buffer.getvalue()
    return None


def convert(png):
    """Yield (target, bytes or None, why) for the WebP files this PNG gets."""
    image = Image.open(png)
    image.load()
    jobs = [(png.with_suffix(".webp"), image)]
    if png.stem in FIXED:
        width, height = FIXED[png.stem]
        jobs.append((png.with_name(f"{png.stem}-2x.webp"), image.resize((width * 2, height * 2), Image.Resampling.LANCZOS)))
    for target, picture in jobs:
        if target.exists():
            yield target, None, "exists"
            continue
        data = encode(picture)
        if data is None:
            yield target, None, "not lossless"
        elif len(data) >= png.stat().st_size:
            yield target, None, f"not smaller ({len(data):,} bytes)"
        else:
            with open(target, "xb") as out:      # "x": never overwrite
                out.write(data)
            yield target, data, "written"


def main(folder):
    written = 0
    for png in sorted(folder.glob("*.png")):
        for target, data, why in convert(png):
            before, after = png.stat().st_size, len(data) if data else 0
            written += after
            print(f"{target.name:34} {before:>9,} -> {after:>9,}  {'-' + str(round(100 * (1 - after / before))) + '%' if data else why}")
    print(f"{'WebP bytes written':34} {written:>9,}")


if __name__ == "__main__":
    main(Path(sys.argv[1]) if len(sys.argv) > 1 else ASSETS)
