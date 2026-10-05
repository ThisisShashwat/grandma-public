"""Data only: the starting subcategory exclusions of the demands (docs/projects.md "Switching the category or the subcategory"). They are
Claude's CONTENT GUESS, conservative on purpose: the owner reviews and edits them in the admin under Demands. A demand is matched by name
and a subcategory by its category's slug and its name, and anything not found is skipped, so a database the owner has already edited cannot
break it. Adding a link that exists changes nothing (idempotent). Going back removes exactly the links listed here and no others."""
from django.db import migrations

EXCLUSIONS = {      # demand name: [(category slug, subcategory name)]
    "Single File": [("software", "Mobile app"), ("web", "Browser extension")],
    "Big Print": [("software", "Command line tool"), ("software", "Bot"), ("software", "Library or package")],
    "Two Colors": [("software", "Bot"), ("software", "Library or package")],
    "One Button": [("software", "Bot"), ("software", "Library or package")],
    "Audio Only": [("software", "Library or package")],
    "Offline": [("software", "Bot")],
    "Sixty Seconds": [("gamedev", "Game tool")],
}


def found(apps):
    """The (demand, subcategory) pairs of EXCLUSIONS whose rows exist."""
    Demand, Subcategory = apps.get_model("projects", "Demand"), apps.get_model("projects", "Subcategory")
    for name, subcategories in EXCLUSIONS.items():
        demand = Demand.objects.filter(name=name).first()
        for slug, subcategory_name in subcategories if demand else ():
            subcategory = Subcategory.objects.filter(category__slug=slug, name=subcategory_name).first()
            if subcategory:
                yield demand, subcategory


def add(apps, schema_editor):
    for demand, subcategory in found(apps):
        demand.excluded_subcategories.add(subcategory)


def remove(apps, schema_editor):
    for demand, subcategory in found(apps):
        demand.excluded_subcategories.remove(subcategory)


class Migration(migrations.Migration):
    dependencies = [("projects", "0016_demand_excluded_subcategories")]
    operations = [migrations.RunPython(add, remove)]
