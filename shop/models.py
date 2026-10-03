"""The Pantry's data, edited in the Django admin (shop/admin.py).

Every item is a Hack Club Bank card grant, except the few "by hand" ones (a letter from HQ, a loot box) that staff fulfil.
Dollar values of grants are public; the rate class (markup) is not. Pages never see these models: shop/catalog.py hands
out plain dataclasses of public fields (docs/security.md).

Layers: pricing.py (pure maths) <- models.py <- catalog.py <- views.py.
"""
import re
from decimal import Decimal

from django.contrib.staticfiles import finders
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import F, Q

from program import payout

from . import pricing

ART_NAME = re.compile(r"[A-Za-z0-9_-]+\.(png|jpg|webp|gif)")


def validate_art(name):
    """Art is a file name inside static/assets (no folders, so it cannot point anywhere else), and the file has to exist."""
    if not ART_NAME.fullmatch(name):
        raise ValidationError("A file name like grandma-cookie-jar.png, no folders.")
    if not finders.find(f"assets/{name}"):
        raise ValidationError(f"There is no {name} in static/assets.")


class RateClass(models.Model):
    """How dear a family of items is. cookies per dollar = program.payout cookies_per_usd x markup."""
    slug = models.SlugField(unique=True)
    name = models.CharField(max_length=60)
    markup = models.DecimalField(
        max_digits=5, decimal_places=3, validators=[MinValueValidator(Decimal("0.001"))],
        help_text="Prices are stored when an item is saved: after changing this, run Recompute prices on the items.",
    )

    class Meta:
        ordering = ["markup"]
        constraints = [models.CheckConstraint(condition=Q(markup__gt=0), name="rateclass_markup_positive")]

    def __str__(self):
        return self.name

    @property
    def cookies_per_usd(self):
        return payout.CONFIG["cookies_per_usd"] * self.markup


class ShopItem(models.Model):
    class Kind(models.TextChoices):
        GRANT = "grant", "Card grant"
        MANUAL = "manual", "By hand"

    class Category(models.TextChoices):         # the shelves of the page, in this order; the owner edits the list later
        HARDWARE = "hardware", "Hardware"
        SOFTWARE = "software", "Software"
        CREDITS = "credits", "Credits"
        FUN = "fun", "Fun"
        JOKE = "joke", "Jokes"

    slug = models.SlugField(unique=True)
    name = models.CharField(max_length=80)
    tagline = models.CharField(max_length=120, blank=True)
    description = models.TextField(blank=True)
    art = models.CharField(max_length=80, default="cookie.png", validators=[validate_art],
                           help_text="A file inside static/assets, for example grandma-cookie-jar.png.")
    kind = models.CharField(max_length=10, choices=Kind.choices, default=Kind.GRANT,
                            help_text="Everything is a card grant unless it cannot be: those staff hand over themselves.")
    category = models.CharField(max_length=10, choices=Category.choices, help_text="Which shelf of the page it sits on.")
    rate_class = models.ForeignKey(RateClass, on_delete=models.PROTECT, related_name="items")
    usd_value = models.DecimalField("dollar value", max_digits=8, decimal_places=2, validators=[MinValueValidator(Decimal("0.01"))],
                                    help_text="A grant's value on the card. Shown to visitors for grants. For a by-hand item it is just our cost.")
    cookies = models.PositiveIntegerField(editable=False)
    cookies_override = models.PositiveIntegerField(null=True, blank=True, validators=[MinValueValidator(1)],
                                                   help_text="Optional. Forces this exact price instead of the computed one.")
    stackable = models.BooleanField(default=False, help_text="Can be bought more than once and the copies add up.")
    max_per_user = models.PositiveIntegerField(null=True, blank=True, validators=[MinValueValidator(1)],
                                               help_text="Empty = no limit. A non-stackable item is always one per person.")
    stock = models.PositiveIntegerField(null=True, blank=True, help_text="What is left. Empty = unlimited, 0 = sold out. Each order takes from it and a rejected or cancelled order gives it back.")
    base_item = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.PROTECT, related_name="upgrades", limit_choices_to={"base_item__isnull": True},
        help_text="Set this to make the item an UPGRADE of that base grant: it tops up the same card and is never sold alone.",
    )
    needs_project = models.BooleanField(
        default=False, help_text="A hardware grant: bought for one specific shipped hardware design, with every part listed. "
                                 "It sits in the separate Hardware section of the shop.")
    active = models.BooleanField(default=True)
    sort_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["sort_order", "name"]
        constraints = [
            models.CheckConstraint(condition=Q(cookies__gt=0), name="shopitem_cookies_positive"),
            models.CheckConstraint(condition=Q(usd_value__gt=0), name="shopitem_usd_positive"),
            models.CheckConstraint(condition=Q(cookies_override__isnull=True) | Q(cookies_override__gte=1), name="shopitem_override_positive"),
            models.CheckConstraint(condition=Q(max_per_user__isnull=True) | Q(max_per_user__gte=1), name="item_max_per_user_positive"),
            models.CheckConstraint(condition=Q(stackable=True) | Q(max_per_user__isnull=True) | Q(max_per_user=1),
                                   name="item_one_per_user_when_not_stackable"),
            models.CheckConstraint(condition=~Q(base_item=F("id")), name="item_not_its_own_base"),
        ]

    def __str__(self):
        return self.name

    @property
    def effective_cookies(self):
        return self.cookies_override or self.cookies

    def cookies_per_dollar(self):
        return Decimal(self.effective_cookies) / Decimal(self.usd_value)

    def compute_cookies(self):
        return pricing.cookie_price(self.usd_value, payout.CONFIG["cookies_per_usd"], self.rate_class.markup)

    def save(self, *args, **kwargs):
        self.cookies = self.compute_cookies()           # from dollars and rate, never from the override; stored so it never moves by itself
        super().save(*args, **kwargs)

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
        if self.kind != self.Kind.GRANT or base.kind != self.Kind.GRANT:
            return "An upgrade and its base must both be card grants: the upgrade tops up the base's card."
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
        if self.needs_project and (self.kind != self.Kind.GRANT or self.base_item_id):
            raise ValidationError({"needs_project": "Only a card grant that is not an upgrade can be tied to a hardware project."})
        if problem := self.upgrade_problem():
            raise ValidationError({"base_item": problem})
