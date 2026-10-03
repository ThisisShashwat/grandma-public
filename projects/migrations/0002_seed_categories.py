"""Starting data: the six categories and a few DUMMY subcategories the owner edits in the admin. Electronics and CAD are hardware
(the two-ship exception for them comes later). Never touches rows that already exist and is not reversed on purpose: rolling
back must not delete rows the owner has edited."""
from django.db import migrations

CATEGORIES = [      # slug, name, kind
    ("web", "Web", "software"), ("software", "Software", "software"), ("gamedev", "Gamedev", "software"),
    ("electronics", "Electronics", "hardware"), ("cad", "CAD", "hardware"), ("other", "Other", "software"),
]
SUBCATEGORIES = {   # dummy entries: edit them in the admin
    "web": ["Website", "Web app", "Browser extension", "Web tool"],
    "software": ["Command line tool", "Desktop app", "Mobile app", "Bot", "Library or package"],
    "gamedev": ["Platformer", "Puzzle game", "Arcade game", "Text adventure", "Game tool"],
    "electronics": ["Sensor or tracker", "Wearable", "Robot or vehicle", "Smart home gadget", "Lights or display"],
    "cad": ["Case or enclosure", "Mechanical part", "Wearable or jewelry", "Toy or game piece", "Home or desk gadget"],
    "other": ["Art or music", "Something else"],
}


def create(apps, schema_editor):
    Category, Subcategory = apps.get_model("projects", "Category"), apps.get_model("projects", "Subcategory")
    for order, (slug, name, kind) in enumerate(CATEGORIES, start=1):
        category, _ = Category.objects.get_or_create(slug=slug, defaults={"name": name, "kind": kind, "sort": order * 10})
        for number, sub in enumerate(SUBCATEGORIES[slug], start=1):
            Subcategory.objects.get_or_create(category=category, name=sub, defaults={"sort": number * 10})


class Migration(migrations.Migration):
    dependencies = [("projects", "0001_initial")]
    operations = [migrations.RunPython(create, migrations.RunPython.noop)]
