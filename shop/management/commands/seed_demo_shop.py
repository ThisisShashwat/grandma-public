"""Fill the shop with DUMMY items so the page can be looked at. A development tool: NEVER run it in production.

    python manage.py seed_demo_shop

Idempotent (run it twice, get the same shop) and refuses to run unless DEBUG is on. Every number and name here is made
up, and every description starts with "Demo data." The real items are entered by the owner in the admin; the migrations
create only the rate classes.
"""
from decimal import Decimal

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from shop.models import RateClass, ShopItem

HAND = ShopItem.Kind.MANUAL
RIBBON, FAVS, GRANTS, STUFF, JOKES = ShopItem.Category.values


def put(slug, rate, usd, description, **fields):
    """Create or update one item, checked by the same rules as the admin."""
    item = ShopItem.objects.filter(slug=slug).first() or ShopItem(slug=slug)
    fields = {"description": f"Demo data. {description}", "rate_class": RateClass.objects.get(slug=rate), "usd_value": Decimal(usd), **fields}
    for key, value in fields.items():
        setattr(item, key, value)
    item.full_clean()
    item.save()
    return item


def seed_grants():
    put("demo-ai-credits", "build", "5", "Credits for an AI coding assistant. Grandma still reads every line it writes.",
        name="AI credits", category=GRANTS, tagline="Robots to type for you. I suppose, dear.", art="grandma-magnifier.png", stackable=True, max_per_user=20, sort_order=1)
    put("demo-hosting-credits", "build", "10", "Credits for a server somewhere that is not Grandma's spare room.",
        name="Hosting credits", category=GRANTS, tagline="A computer in somebody else's house. Quieter.", art="grandma-peek.png", stackable=True, max_per_user=10, sort_order=2)
    put("demo-pcb-credits", "build", "15", "Credits for printed circuit boards and 3D prints.",
        name="PCB and 3D print credits", category=GRANTS, tagline="For little green boards and plastic things. Do not eat.", art="grandma-writing.png",
        stackable=True, max_per_user=10, sort_order=3)
    put("demo-domain", "build", "11", "A domain name for a year.",
        name="Domain credit", category=GRANTS, tagline="Your very own address. Mind the typos.", art="grandma-finger.png", sort_order=4)
    put("demo-software-licence", "build", "40", "One software licence, bought by you with the grant.",
        name="Software licence grant", category=GRANTS, tagline="Not the pirate kind. Grandma asked.", art="grandma-book.png", sort_order=5)

    ipad = put("demo-ipad", "build", "329", "A basic iPad, as a card grant.",
               name="iPad", category=STUFF, tagline="A tablet, dear. Swiping is not a hobby.", art="grandma-wave.png", sort_order=7)
    put("demo-ipad-upgrade", "upgrade", "25",
        "Tops up the same card as the iPad grant and is never sold alone. Add 20 of these and the iPad becomes a fancy Samsung tablet.",
        name="iPad upgrade", category=STUFF, base_item=ipad, stackable=True, max_per_user=20)

    put("demo-game-console", "fun", "300", "A console, as a card grant. The fun rate class: dearer per dollar.",
        name="Game console", category=STUFF, tagline="Rest is important. Once.", art="grandma-shocked.png", sort_order=8)


def seed_by_hand():
    put("demo-face", "fun", "2", "A photo, printed and posted by staff.",
        name="Shashwat's face, printed", category=JOKES, tagline="A nice face. Mostly.", art="grandma-smiley.png", kind=HAND, stock=30, sort_order=20)
    put("demo-hq-letter", "fun", "1.5", "A surprise letter, handed over by staff.",
        name="A letter from HQ", category=JOKES, tagline="Could be a thank you. Could be a bill. Grandma is not allowed to say.", art="grandma-complaints.png",
        kind=HAND, sort_order=21)
    put("demo-loot-box", "fun", "10", "Whatever staff put in the box.",
        name="Mystery loot box", category=JOKES, tagline="Grandma packs it herself. Do not shake it.", art="grandma-cookie-jar.png",
        kind=HAND, stackable=True, max_per_user=3, stock=25, sort_order=22)
    put("demo-nothing", "fun", "0.01", "You get nothing. It sells very well.",
        name="Nothing", category=JOKES, tagline="Absolutely nothing. It is very popular.", art="mood-0-asleep.png",
        kind=HAND, stackable=True, max_per_user=10, sort_order=23)
    put("demo-strong-letter", "fun", "1", "A letter from Grandma.",
        name="A strongly worded letter", category=JOKES, tagline="From Grandma. About your posture.", art="grandma-finger-wag.png", kind=HAND, sort_order=24)
    put("demo-recipe", "fun", "1", "A recipe card.",
        name="Grandma's cookie recipe", category=JOKES, tagline="One ingredient is missing. She will not say which.", art="cookie.png", kind=HAND, sort_order=25)
    put("demo-phone-call", "fun", "3", "A phone call, booked by staff.",
        name="A phone call from Grandma", category=JOKES, tagline="Two minutes. She will ask if you are eating.", art="grandma-phone.png", kind=HAND, sort_order=26)
    put("demo-sock", "fun", "2", "A sold out item, to see the sold out badge.",
        name="One sock", category=JOKES, tagline="The other one is gone. Sold out, dear.", art="grandma-sad-x.png", kind=HAND, stock=0, sort_order=27)


class Command(BaseCommand):
    help = "Create or refresh dummy shop items (development only)."

    def handle(self, *args, **options):
        if not settings.DEBUG:
            raise CommandError("seed_demo_shop is a development tool: it refuses to run with DEBUG off.")
        seed_grants()
        seed_by_hand()
        self.stdout.write(f"{ShopItem.objects.count()} demo items ready: open /shop/")
