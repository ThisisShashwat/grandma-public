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
class Choice:
    """One project a hardware grant may be for."""
    id: str
    name: str
    where: str                  # "Electronics, Sensors"


@dataclass(frozen=True)
class Sheet:
    slug: str
    name: str
    tagline: str
    art: str
    description: str
    hardware: bool
    manual: bool                # staff hand it over: no link, no cart
    stackable: bool
    cookies: int
    value: Decimal
    most: int                   # the most the person may take in one order
    held: int                   # how many they hold already
    balance: int
    blocked: str                # Grandma's sentence when nothing can be ordered right now, "" when it can
    options: tuple              # Option records (plain grants)
    choices: tuple              # Choice records (hardware grants)
    max_parts: int
    up_name: str                # hardware: the upgrade the order adds by itself, "" if the grant has none
    up_cookies: int
    up_value: Decimal
    up_most: int | None


def option(upgrade):
    return Option(f"up_{upgrade.pk}", upgrade.name, upgrade.effective_cookies, upgrade.usd_value, upgrade.max_per_user)


def choice(project):
    return Choice(str(project.pk), project.name, project.category.name + (f", {project.subcategory.name}" if project.subcategory else ""))


def most_of(item, held):
    """How many of the grant one order may take: what the person may still hold, never more than the stock or the ceiling."""
    cap = rules.MAX_QUANTITY if item.stackable and item.max_per_user is None else (item.max_per_user if item.stackable else 1)
    left = max(min(cap - held, rules.MAX_QUANTITY), 0)
    return left if item.stock is None else min(left, item.stock)


def blocked_for(item, held, choices, balance):
    """Why the page offers no form: sold out, held already, nobody to buy it for, or not enough cookies even for one."""
    if problem := rules.stock_problem(item.stock, 1) or rules.limit_problem(item.stackable, item.max_per_user, held, 1):
        return problem
    if item.needs_project and not choices:
        return "no projects"
    return rules.afford_problem(balance, item.effective_cookies)


def build(user, item, cfg, balance):
    """The sheet for `item` (a base grant from services.gettable) and this person."""
    held = services.held(user, item.pk)
    choices = tuple(choice(p) for p in services.eligible_projects(user, item)) if item.needs_project else ()
    best = rules.best_upgrade([(u.pk, u.effective_cookies, u.usd_value) for u in item.live_upgrades]) if item.needs_project else None
    chosen = next((u for u in item.live_upgrades if best and u.pk == best[0]), None)
    return Sheet(
        slug=item.slug, name=item.name, tagline=item.tagline, art=item.art, description=item.description, hardware=item.needs_project,
        manual=item.kind == item.Kind.MANUAL, stackable=item.stackable and not item.needs_project, cookies=item.effective_cookies, value=item.usd_value,
        most=most_of(item, held) if not item.needs_project else 1, held=held, balance=balance, blocked=blocked_for(item, held, choices, balance),
        options=() if item.needs_project else tuple(option(u) for u in item.live_upgrades), choices=choices, max_parts=cfg.ORDER_MAX_PARTS,
        up_name=chosen.name if chosen else "", up_cookies=chosen.effective_cookies if chosen else 0, up_value=chosen.usd_value if chosen else Decimal(0),
        up_most=chosen.max_per_user if chosen else None)
