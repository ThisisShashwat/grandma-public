"""A few Pantry items for the home page (admin setting HOME_PANTRY_PEEK, docs/shop.md "The home page peek").

The home page is public, so this always reads the shop as a visitor sees it: never a ribbon only item, even when the viewer holds a Blue Ribbon.
It hands out the same frozen Product records as the Pantry, never a model.
"""
from itertools import islice

from . import catalog


def pick(count):
    """The first `count` items of the Pantry in shop order (shelf by shelf), skipping the by hand ones and the sold out ones, which a peek
    does not need. 0 means the peek is switched off: nothing is read, no query is made. An empty shop gives an empty tuple."""
    if not count:
        return ()
    shelved = (product for shelf in catalog.build(ribbon=False).shelves for product in shelf.products)
    return tuple(islice((p for p in shelved if p.available and not p.manual), count))
