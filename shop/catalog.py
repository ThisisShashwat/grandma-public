"""The public side of the shop: what a visitor may see, as plain frozen dataclasses.

This is the privacy boundary (docs/security.md). Templates only ever receive these objects, never a model instance, so
anything not listed here (the rate class, the markup, a by-hand item's cost, the override, inactive items) cannot leak
through a template by accident. A grant's dollar value IS public, on purpose (owner's decision, docs/decisions.md).
Add a field only after asking whether a visitor may know it. `ribbon_only` and `locked` are public on purpose (owner, 2026-10-16): everybody sees
every active item, and a ribbon only one shows locked for anybody who holds no Blue Ribbon.
"""
from dataclasses import dataclass
from decimal import Decimal

from django.db.models import Prefetch

from program import payout

from .models import ShopItem

BLURBS = {        # Grandma's line under each shelf, keyed by ShopItem.Category. The shelves follow the order of that list.
    "hardware": "Real parts for real things. Grandma likes a receipt.",
    "software": "The grown-up programs, paid for.",
    "credits": "Pay-as-you-go things for your project. Receipts, please.",
    "fun": "Things you want, not things you need. Grandma allows some.",
    "joke": "Grandma does these by hand. Do not ask how, and do not ask why.",
}


@dataclass(frozen=True)
class Upgrade:
    name: str
    value_usd: Decimal
    cookies: int
    max_per_user: int | None        # None = no limit
    locked: bool                    # ribbon only and the viewer holds no Blue Ribbon


@dataclass(frozen=True)
class Product:
    slug: str
    name: str
    tagline: str
    description: str
    art: str
    category: str
    kind: str                       # the label: "Card grant" or "By hand"
    manual: bool
    stackable: bool
    max_per_user: int | None        # 1 for anything non-stackable, None = no limit
    stock_left: int | None          # None = unlimited
    available: bool                 # False once the stock is gone
    cookies: int
    value_usd: Decimal | None       # the grant's value on the card; None for a by-hand item
    hours_low: int                  # about how many hours of work the price is
    hours_high: int
    upgrades: tuple[Upgrade, ...]
    ribbon_only: bool               # only Blue Ribbon holders may buy it (it is shown to everybody)
    locked: bool                    # ribbon_only and the viewer holds no Blue Ribbon


@dataclass(frozen=True)
class Shelf:
    key: str
    title: str
    blurb: str
    products: tuple[Product, ...]


@dataclass(frozen=True)
class Catalog:
    shelves: tuple[Shelf, ...]


def _upgrade(item, ribbon):
    return Upgrade(item.name, item.usd_value, item.effective_cookies, item.max_per_user, item.ribbon_only and not ribbon)


def _product(item, ribbon):
    grant = item.kind == ShopItem.Kind.GRANT
    low, high = payout.hours_range(item.effective_cookies)
    return Product(
        slug=item.slug, name=item.name, tagline=item.tagline, description=item.description, art=item.art_source,
        category=item.category, kind=item.get_kind_display(), manual=not grant, stackable=item.stackable,
        max_per_user=item.max_per_user if item.stackable else 1, stock_left=item.stock, available=item.stock != 0,
        cookies=item.effective_cookies, value_usd=item.usd_value if grant else None, hours_low=low, hours_high=high,
        upgrades=tuple(_upgrade(up, ribbon) for up in item.live_upgrades), ribbon_only=item.ribbon_only, locked=item.ribbon_only and not ribbon,
    )


def _shelves(products):
    shelves = ((key, title, BLURBS.get(key, ""), tuple(p for p in products if p.category == key)) for key, title in ShopItem.Category.choices)
    return tuple(Shelf(*shelf) for shelf in shelves if shelf[3])


def build(*, ribbon=False):
    """The shop as one viewer sees it. The only function the views call. Every active item and upgrade is listed; `ribbon` says the viewer holds a
    Blue Ribbon, and without one the ribbon only items and upgrades come out `locked` (buying them is refused in orders/, not here). Nothing is
    cached, so one viewer's shelves never reach another."""
    upgrades = Prefetch("upgrades", ShopItem.objects.filter(active=True), to_attr="live_upgrades")
    items = ShopItem.objects.filter(active=True, base_item__isnull=True).prefetch_related(upgrades)
    products = [_product(item, ribbon) for item in items]
    return Catalog(shelves=_shelves(products))
