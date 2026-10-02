"""The public side of the shop: what a visitor may see, as plain frozen dataclasses.

This is the privacy boundary (docs/security.md). Templates and JSON only ever receive these objects, never a model
instance, so a dollar value, a rate class or a markup cannot leak through a template by accident: those fields do
not exist here. Add a field to a dataclass only after asking whether a visitor may know it.
"""
from dataclasses import dataclass

from django.conf import settings
from django.db.models import Prefetch

from .models import Region, RegionalPrice, ShopItem


@dataclass(frozen=True)
class Upgrade:
    name: str
    cookies: int
    max_per_user: int | None


@dataclass(frozen=True)
class Product:
    slug: str
    name: str
    tagline: str
    description: str
    art: str
    kind: str                       # the label: "Card grant", "Shipped", "Digital"
    category: str
    stackable: bool
    max_per_user: int | None        # 1 for anything non-stackable, None = no limit
    stock_left: int | None          # None = unlimited
    cookies: int                    # in the chosen region
    available: bool                 # False once the stock is gone
    upgrades: tuple[Upgrade, ...]


@dataclass(frozen=True)
class Shelf:
    key: str
    label: str
    products: tuple[Product, ...]


@dataclass(frozen=True)
class RegionChoice:
    code: str
    name: str
    current: bool


@dataclass(frozen=True)
class Catalog:
    regions: tuple[RegionChoice, ...]
    shelves: tuple[Shelf, ...]


def pick_region(regions, code):
    """The region asked for, else the default, else the first active one, else None (no regions at all)."""
    by_code = {region.code: region for region in regions}
    return by_code.get((code or "").upper()) or by_code.get(settings.SHOP_DEFAULT_REGION) or (regions[0] if regions else None)


def _in_region(region):
    return Prefetch("regional_prices", RegionalPrice.objects.filter(region=region), to_attr="here")


def _price_here(item):
    """Cookies in the prefetched region, or None when the item is switched off there. No row = the item's own price."""
    if not item.here:
        return item.effective_cookies
    row = item.here[0]
    return row.effective_cookies if row.enabled else None


def _upgrades(item):
    prices = ((up, _price_here(up)) for up in item.live_upgrades)
    return tuple(Upgrade(up.name, cookies, up.max_per_user) for up, cookies in prices if cookies is not None)


def _product(item):
    cookies = _price_here(item)
    if cookies is None:
        return None
    return Product(
        slug=item.slug, name=item.name, tagline=item.tagline, description=item.description, art=item.art,
        kind=item.get_kind_display(), category=item.category, stackable=item.stackable,
        max_per_user=item.max_per_user if item.stackable else 1, stock_left=item.stock,
        cookies=cookies, available=item.stock != 0, upgrades=_upgrades(item),
    )


def _shelves(products):
    shelves = ((key, label, tuple(p for p in products if p.category == key)) for key, label in ShopItem.Category.choices)
    return tuple(Shelf(key, label, items) for key, label, items in shelves if items)


def build(region_code):
    """The whole public shop for the region asked for. The only function the views call."""
    regions = list(Region.objects.filter(active=True))
    region = pick_region(regions, region_code)
    upgrades = ShopItem.objects.filter(active=True).prefetch_related(_in_region(region))
    items = (ShopItem.objects.filter(active=True, base_item__isnull=True)
             .prefetch_related(_in_region(region), Prefetch("upgrades", upgrades, to_attr="live_upgrades")))
    products = [product for item in items if (product := _product(item))]
    return Catalog(
        regions=tuple(RegionChoice(r.code, r.name, r == region) for r in regions),
        shelves=_shelves(products),
    )
