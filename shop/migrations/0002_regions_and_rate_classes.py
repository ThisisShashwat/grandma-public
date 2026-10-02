"""Starting data: the seven regions other Hack Club shops use, and three DUMMY rate classes the owner edits in the admin.
Never creates items. Not reversed on purpose: rolling back must not delete rows the owner has edited."""
from django.db import migrations

REGIONS = [
    ("US", "USA"), ("EU", "European Union"), ("UK", "United Kingdom"), ("IN", "India"),
    ("CA", "Canada"), ("AU", "Australia and NZ"), ("XX", "Rest of world"),
]
RATE_CLASSES = [("build", "Build", "1.10"), ("fun", "Fun", "1.30"), ("upgrade", "Upgrade", "1.50")]    # dummy markups


def create(apps, schema_editor):
    Region, RateClass = apps.get_model("shop", "Region"), apps.get_model("shop", "RateClass")
    for order, (code, name) in enumerate(REGIONS, start=1):
        Region.objects.get_or_create(code=code, defaults={"name": name, "sort_order": order * 10})
    for slug, name, markup in RATE_CLASSES:
        RateClass.objects.get_or_create(slug=slug, defaults={"name": name, "markup": markup})


class Migration(migrations.Migration):
    dependencies = [("shop", "0001_initial")]
    operations = [migrations.RunPython(create, migrations.RunPython.noop)]
