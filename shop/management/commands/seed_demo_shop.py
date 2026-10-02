"""Fill the shop with DUMMY items so the page can be looked at. A development tool: NEVER run it in production.

    python manage.py seed_demo_shop

Idempotent (run it twice, get the same shop) and refuses to run unless DEBUG is on. Every dollar figure and name here is
made up. The real items are entered by the owner in the admin; the migrations create only regions and rate classes.
"""
from decimal import Decimal

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from shop.models import RateClass, Region, RegionalPrice, ShopItem

HARDWARE, SOFTWARE, CREDITS, FUN, SWAG = (ShopItem.Category.HARDWARE, ShopItem.Category.SOFTWARE, ShopItem.Category.CREDITS,
                                          ShopItem.Category.FUN, ShopItem.Category.SWAG)
GRANT, SHIPPED, DIGITAL = ShopItem.Kind.GRANT, ShopItem.Kind.SHIPPED, ShopItem.Kind.DIGITAL

DEMO_NOTE = "DEMO DATA, not a real product."


def put(slug, rate, usd, **fields):
    """Create or update one item, checked by the same rules as the admin."""
    item = ShopItem.objects.filter(slug=slug).first() or ShopItem(slug=slug)
    fields = {"description": DEMO_NOTE, "rate_class": RateClass.objects.get(slug=rate), "usd_value": Decimal(usd), **fields}
    for key, value in fields.items():
        setattr(item, key, value)
    item.full_clean()
    item.save()
    return item


def put_region(item, code, usd, enabled=True):
    RegionalPrice.objects.update_or_create(
        item=item, region=Region.objects.get(code=code), defaults={"usd_value": Decimal(usd), "enabled": enabled})


def seed():
    put("demo-ai-credits", "build", "5", name="AI credits", tagline="Tokens for your coding assistant", art="grandma-magnifier.png",
        kind=DIGITAL, category=CREDITS, stackable=True, max_per_user=20, sort_order=1)
    put("demo-hardware-funding", "build", "25", name="Hardware funding", tagline="Chip in for parts, boards and tools",
        art="grandma-clipboard.png", kind=GRANT, category=HARDWARE, stackable=True, max_per_user=8, sort_order=2)
    put("demo-domain", "build", "11", name="Free domain", tagline="A name for your project, for a year",
        art="grandma-writing.png", kind=GRANT, category=SOFTWARE, sort_order=3)

    ipad = put("demo-ipad", "build", "300", name="iPad", tagline="A card grant for a tablet. Buy upgrades to aim higher",
               art="grandma-phone.png", kind=GRANT, category=HARDWARE, sort_order=4)
    for slug, usd, name, order in (("demo-ipad-small", "50", "Top-up, small", 1), ("demo-ipad-medium", "100", "Top-up, medium", 2),
                                   ("demo-ipad-large", "250", "Top-up, large", 3)):
        put(slug, "upgrade", usd, name=f"iPad {name.lower()}", kind=GRANT, category=HARDWARE, stackable=True, max_per_user=4,
            base_item=ipad, sort_order=order)

    pi = put("demo-raspberry-pi", "build", "90", name="Raspberry Pi kit", tagline="Board, case, cables. Shipped to you",
             art="grandma-nose-up.png", kind=SHIPPED, category=HARDWARE, sort_order=5)
    for code, usd, enabled in (("US", "90", True), ("EU", "105", True), ("UK", "100", True), ("IN", "125", True),
                               ("CA", "110", True), ("AU", "90", False)):
        put_region(pi, code, usd, enabled)

    put("demo-game-console", "fun", "300", name="Game console", tagline="Pure fun, no apologies", art="grandma-shocked.png",
        kind=GRANT, category=FUN, sort_order=6)
    put("demo-mug", "fun", "8", name="Grandma mug", tagline="For tea. Or milk, for the cookies", art="grandma-smiley.png",
        kind=SHIPPED, category=SWAG, stock=40, sort_order=7)
    put("demo-stickers", "fun", "3", name="Sticker sheet", tagline="Sold out, dear. Come back later", art="cookie.png",
        kind=SHIPPED, category=SWAG, stock=0, sort_order=8)


class Command(BaseCommand):
    help = "Create or refresh dummy shop items (development only)."

    def handle(self, *args, **options):
        if not settings.DEBUG:
            raise CommandError("seed_demo_shop is a development tool: it refuses to run with DEBUG off.")
        seed()
        self.stdout.write(f"{ShopItem.objects.count()} demo items ready: open /shop/")
