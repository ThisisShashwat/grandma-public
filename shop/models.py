"""The Pantry's data. Every dollar figure in here is private: it never reaches a template, JSON or log (docs/security.md).
Pages read shop/catalog.py, which hands out plain dataclasses, never these models.

Layers: pricing.py (pure maths) <- models.py <- catalog.py <- views.py. Edited in the Django admin (shop/admin.py)."""
import re
from decimal import Decimal

from django.conf import settings
from django.contrib.staticfiles import finders
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator, RegexValidator
from django.db import models
from django.db.models import F, Q

from program import payout

from . import pricing

MIN_USD = [MinValueValidator(Decimal("0.01"))]
MIN_COOKIES = [MinValueValidator(1)]


ART_NAME = re.compile(r"[A-Za-z0-9_-]+\.(png|jpg|webp|gif)")


def validate_art(name):
    """Art is a file name inside static/assets (no folders, so it cannot point anywhere else), and the file has to exist."""
    if not ART_NAME.fullmatch(name):
        raise ValidationError("A file name like grandma-cookie-jar.png, no folders.")
    if not finders.find(f"assets/{name}"):
        raise ValidationError(f"There is no {name} in static/assets.")


def cookie_price(usd, rate_class, slug, region_code):
    """One unit's cookie price. The only place the pure maths meets Django settings."""
    return pricing.cookie_price(
        usd, payout.CONFIG["cookies_per_usd"], rate_class.markup,
        settings.SHOP_PRICE_SECRET.encode(), slug, region_code,
    )


class Region(models.Model):
    code = models.CharField(max_length=8, unique=True, validators=[RegexValidator(r"\A[A-Z]+\Z", "Capital letters only, like US or XX.")])
    name = models.CharField(max_length=60)
    sort_order = models.PositiveSmallIntegerField(default=0)
    active = models.BooleanField(default=True, help_text="Only active regions can be picked with ?region=CODE.")

    class Meta:
        ordering = ["sort_order", "code"]

    def __str__(self):
        return f"{self.name} ({self.code})"


class RateClass(models.Model):
    """How dear a family of items is. cookies per dollar = program.payout cookies_per_usd x markup."""
    slug = models.SlugField(unique=True)
    name = models.CharField(max_length=60)
    markup = models.DecimalField(
        max_digits=5, decimal_places=3, validators=[MinValueValidator(Decimal("0.001"))],
        help_text="PRIVATE. Prices are stored when an item is saved: after changing this, run Recompute prices on the items.",
    )

    class Meta:
        ordering = ["markup"]
        constraints = [models.CheckConstraint(condition=Q(markup__gt=0), name="rateclass_markup_positive")]

    def __str__(self):
        return self.name

    @property
    def cookies_per_usd(self):
        return payout.CONFIG["cookies_per_usd"] * self.markup


class Priced(models.Model):
    """A dollar value with a stored cookie price: the item itself, or its price in one region."""
    usd_value = models.DecimalField("dollar value (private)", max_digits=8, decimal_places=2, validators=MIN_USD,
                                    help_text="PRIVATE. What one unit costs us. Never shown to visitors.")
    cookies = models.PositiveIntegerField(editable=False)
    cookies_override = models.PositiveIntegerField(null=True, blank=True, validators=MIN_COOKIES,
                                                   help_text="Optional. Forces this exact price instead of the computed one.")

    class Meta:
        abstract = True
        constraints = [
            models.CheckConstraint(condition=Q(cookies__gt=0), name="%(class)s_cookies_positive"),
            models.CheckConstraint(condition=Q(usd_value__gt=0), name="%(class)s_usd_positive"),
            models.CheckConstraint(condition=Q(cookies_override__isnull=True) | Q(cookies_override__gte=1),
                                   name="%(class)s_override_positive"),
        ]

    @property
    def effective_cookies(self):
        return self.cookies_override or self.cookies

    def cookies_per_dollar(self):
        return Decimal(self.effective_cookies) / Decimal(self.usd_value)

    def save(self, *args, **kwargs):
        self.cookies = self.compute_cookies()           # from usd and rate, never from the override; stored so it never moves by itself
        super().save(*args, **kwargs)


class ShopItem(Priced):
    class Kind(models.TextChoices):
        GRANT = "grant", "Card grant"
        SHIPPED = "shipped", "Shipped"
        DIGITAL = "digital", "Digital"

    class Category(models.TextChoices):
        HARDWARE = "hardware", "Hardware"
        SOFTWARE = "software", "Software"
        CREDITS = "credits", "Credits"
        FUN = "fun", "Fun"
        SWAG = "swag", "Swag"

    slug = models.SlugField(unique=True)
    name = models.CharField(max_length=80)
    tagline = models.CharField(max_length=120, blank=True)
    description = models.TextField(blank=True)
    art = models.CharField(max_length=80, default="cookie.png", validators=[validate_art],
                           help_text="A file inside static/assets, for example grandma-cookie-jar.png.")
    kind = models.CharField(max_length=10, choices=Kind.choices, default=Kind.GRANT)
    category = models.CharField(max_length=10, choices=Category.choices)
    rate_class = models.ForeignKey(RateClass, on_delete=models.PROTECT, related_name="items")
    stackable = models.BooleanField(default=False, help_text="Can be bought more than once and the copies add up.")
    max_per_user = models.PositiveIntegerField(null=True, blank=True, validators=MIN_COOKIES,
                                               help_text="Empty = no limit. A non-stackable item is always one per person.")
    stock = models.PositiveIntegerField(null=True, blank=True, help_text="Empty = unlimited. 0 = sold out.")
    base_item = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.PROTECT, related_name="upgrades", limit_choices_to={"base_item__isnull": True},
        help_text="Set this to make the item an UPGRADE of that base grant. Upgrades are only sold together with their base.",
    )
    active = models.BooleanField(default=True)
    sort_order = models.PositiveSmallIntegerField(default=0)

    class Meta(Priced.Meta):
        ordering = ["sort_order", "name"]
        constraints = Priced.Meta.constraints + [
            models.CheckConstraint(condition=Q(max_per_user__isnull=True) | Q(max_per_user__gte=1), name="item_max_per_user_positive"),
            models.CheckConstraint(condition=Q(stackable=True) | Q(max_per_user__isnull=True) | Q(max_per_user=1),
                                   name="item_one_per_user_when_not_stackable"),
            models.CheckConstraint(condition=~Q(base_item=F("id")), name="item_not_its_own_base"),
        ]

    def __str__(self):
        return self.name

    def compute_cookies(self):
        return cookie_price(self.usd_value, self.rate_class, self.slug, pricing.ITEM_PRICE)

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        for row in self.regional_prices.select_related("region"):
            row.save()                                  # a regional price depends on this item's slug and rate class

    def upgrade_problem(self):
        """Which upgrade rule this item breaks, as a sentence, or "". A base item is checked through its upgrades."""
        if self.base_item_id is None:
            return next(filter(None, (up.upgrade_problem() for up in self.upgrades.all())), "") if self.pk else ""
        base = self.base_item
        if base.pk == self.pk:
            return "An item cannot be its own base."
        if base.base_item_id is not None:
            return "The base item cannot itself be an upgrade."
        if self.pk and self.upgrades.exists():
            return "This item has upgrades of its own, so it cannot be an upgrade."
        if not self.stackable:
            return f"{self.name} must be stackable: an upgrade can be bought several times."
        if not (self.usd_value and self.rate_class_id):
            return ""                                   # the form already complains about the missing price
        if self.cookies_per_dollar() < base.cookies_per_dollar():
            return f"{self.name} would be a better deal than {base.name}. An upgrade must cost at least as many cookies per dollar as its base."
        return ""

    def clean(self):
        if self.rate_class_id and self.usd_value:
            self.cookies = self.compute_cookies()       # so the rate rules below compare the price this save will store
        if not self.stackable and self.max_per_user not in (None, 1):
            raise ValidationError({"max_per_user": "A non-stackable item is one per person: leave this empty or use 1."})
        if problem := self.upgrade_problem():
            raise ValidationError({"base_item": problem})


class RegionalPrice(Priced):
    """An item's price in one region. No row for a region means the item's own price, available there."""
    item = models.ForeignKey(ShopItem, on_delete=models.CASCADE, related_name="regional_prices")
    region = models.ForeignKey(Region, on_delete=models.PROTECT, related_name="prices")
    enabled = models.BooleanField(default=True, help_text="Off = the item is hidden in this region.")

    class Meta(Priced.Meta):
        ordering = ["region__sort_order"]
        constraints = Priced.Meta.constraints + [
            models.UniqueConstraint(fields=["item", "region"], name="one_price_per_item_and_region"),
        ]

    def __str__(self):
        return f"{self.item} in {self.region.code}"

    def compute_cookies(self):
        return cookie_price(self.usd_value, self.item.rate_class, self.item.slug, self.region.code)
