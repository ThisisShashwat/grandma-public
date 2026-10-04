"""Data only: the program is software only, so two stored rules lose their hardware words (Tiny: the 5 cm cube; One Button: the
physical switch). A row is changed only if it still holds the old seeded text, so a rule the owner has edited in the admin is left
alone. Not reversed on purpose."""
from django.db import migrations

CHANGES = {      # name: (the text 0003 seeded, the software only text)
    "Tiny": ("A hard size cap for your category: about 500 lines of code, 10 components, or a 5 cm cube.",
             "A hard size cap for your category: about 500 lines of code or 10 components."),
    "One Button": ("One input controls everything: one key, one tap zone or one physical switch.",
                   "One input controls everything: one key or one tap zone."),
}


def reword(apps, schema_editor):
    Demand = apps.get_model("projects", "Demand")
    for name, (old, new) in CHANGES.items():
        Demand.objects.filter(name=name, rule=old).update(rule=new)


class Migration(migrations.Migration):
    dependencies = [("projects", "0007_remove_category_kind")]
    operations = [migrations.RunPython(reword, migrations.RunPython.noop)]
