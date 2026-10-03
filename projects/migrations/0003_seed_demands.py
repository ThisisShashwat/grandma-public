"""Starting data: the 28 demands, from program/content (POOL for the name, line and tier, demand_rules for the plain rule, the
categories each fits and the blocklist). A demand that fits all five of the main categories also fits Other, which is how
docs/program.md says Other draws only Tiny, Two Colors and No Jargon. The migration reads the Python lists as they are when it
runs: the database is the truth from then on, edited in the admin. Never touches a demand that exists, not reversed on purpose."""
from django.db import migrations

from program.content.demand_rules import CATEGORIES, CONFLICTS, RULES
from program.content.demands import POOL


def create(apps, schema_editor):
    Category, Demand = apps.get_model("projects", "Category"), apps.get_model("projects", "Demand")
    by_name = {c.name: c for c in Category.objects.all()}
    for demand in POOL:
        rule = RULES[demand.name]
        row, made = Demand.objects.get_or_create(name=demand.name, defaults={"grandma_line": demand.line, "rule": rule.plain, "tier": demand.tier})
        if made:
            fits = list(rule.fits) + (["Other"] if len(rule.fits) == len(CATEGORIES) else [])
            row.categories.set([by_name[name] for name in fits])
    for a, b in CONFLICTS:      # both directions by hand: a migration's historical model does not know the field is symmetrical
        first, second = Demand.objects.get(name=a), Demand.objects.get(name=b)
        first.conflicts.add(second)
        second.conflicts.add(first)


class Migration(migrations.Migration):
    dependencies = [("projects", "0002_seed_categories")]
    operations = [migrations.RunPython(create, migrations.RunPython.noop)]
