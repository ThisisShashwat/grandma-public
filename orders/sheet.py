"""What the order page's template may know about one grant and one person: frozen records of plain fields, never a model (the same boundary as
shop/catalog.py and dashboard/records.py). Built from the shop item and the person's own rows only, so there is nothing to guess."""
from dataclasses import dataclass
from decimal import Decimal

from orders import rules, services


@dataclass(frozen=True)
class Option:
    """One upgrade the person may add to a plain grant: `field` is the form field that carries its count."""
    field: str
    name: str
    cookies: int
    value: Decimal
    most: int | None            # per order; None = no limit


@dataclass(frozen=True)
class Sheet:
    slug: str
    name: str
    tagline: str
    art: str
    description: str
    manual: bool                # staff hand it over: no link, no cart
    stackable: bool
    cookies: int
    value: Decimal | None       # a grant's value on the card; None for a by-hand item (its cost never leaves the database)
    most: int                   # the most the person may take in one order
    held: int                   # how many they hold already
    balance: int
    blocked: str                # Grandma's sentence when nothing can be ordered right now, "" when it can
    options: tuple              # Option records (plain grants)


def option(upgrade):
    return Option(f"up_{upgrade.pk}", upgrade.name, upgrade.effective_cookies, upgrade.usd_value, upgrade.max_per_user)


def most_of(item, held):
    """How many of the grant one order may take: what the person may still hold, never more than the stock or the ceiling."""
    cap = rules.MAX_QUANTITY if item.stackable and item.max_per_user is None else (item.max_per_user if item.stackable else 1)
    left = max(min(cap - held, rules.MAX_QUANTITY), 0)
    return left if item.stock is None else min(left, item.stock)


def blocked_for(item, held, balance, ribbon):
    """Why the page offers no form: a ribbon only grant and no Blue Ribbon (`ribbon`), sold out, held already, or not enough cookies even for one."""
    if item.ribbon_only and not ribbon:
        return services.RIBBON_ONLY
    if problem := rules.stock_problem(item.stock, 1) or rules.limit_problem(item.stackable, item.max_per_user, held, 1):
        return problem
    return rules.afford_problem(balance, item.effective_cookies)


def build(user, item, cfg, balance, ribbon):
    """The sheet for `item` (a base grant from services.gettable) and this person; `ribbon` says they hold a Blue Ribbon."""
    held = services.held(user, item.pk)
    return Sheet(
        slug=item.slug, name=item.name, tagline=item.tagline, art=item.art, description=item.description,
        manual=item.kind == item.Kind.MANUAL, stackable=item.stackable, cookies=item.effective_cookies, value=item.usd_value if item.kind == item.Kind.GRANT else None,
        most=most_of(item, held), held=held, balance=balance, blocked=blocked_for(item, held, balance, ribbon),
        options=tuple(option(u) for u in item.live_upgrades))
