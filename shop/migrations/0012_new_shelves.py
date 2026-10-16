"""The Pantry shelves change: Blue Ribbon, Grandma's favs, Grants, Stuff, Jokes (the owner, 2026-10-17). The stored `category` of the items already
there moves to the nearest new shelf; nothing else on an item is touched. Both directions only rename the value, so running either twice changes nothing."""
from django.db import migrations, models

FORWARD = {"hardware": "grants", "software": "grants", "credits": "grants", "fun": "stuff", "joke": "jokes"}
BACKWARD = {"grants": "hardware", "stuff": "fun", "jokes": "joke", "ribbon": "fun", "favs": "fun"}      # best effort: the old list had no shelf for the last two


def rename(apps, mapping):
    ShopItem = apps.get_model("shop", "ShopItem")
    for old, new in mapping.items():
        ShopItem.objects.filter(category=old).update(category=new)


def to_new_shelves(apps, schema_editor):
    rename(apps, FORWARD)


def to_old_shelves(apps, schema_editor):
    rename(apps, BACKWARD)


class Migration(migrations.Migration):

    dependencies = [
        ('shop', '0011_shopitem_ribbon_only_help'),
    ]

    operations = [
        migrations.AlterField(
            model_name='shopitem',
            name='category',
            field=models.CharField(choices=[('ribbon', 'Blue Ribbon'), ('favs', "Grandma's favs"), ('grants', 'Grants'), ('stuff', 'Stuff'), ('jokes', 'Jokes')], help_text='Which shelf of the page it sits on.', max_length=10),
        ),
        migrations.RunPython(to_new_shelves, to_old_shelves),
    ]
