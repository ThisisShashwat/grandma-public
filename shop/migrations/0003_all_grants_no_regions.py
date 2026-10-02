"""Spec change 2026-10-03: no regional pricing, no categories, kinds are grant or by hand. 0001 and 0002 stay as they were
(applied migrations are never edited); this one drops what the owner no longer wants."""

import django.core.validators
import django.db.models.deletion
from decimal import Decimal
from django.db import migrations, models


def kinds_to_grant_or_manual(apps, schema_editor):
    """Everything is a card grant now. The old shipped items need staff to hand them over; digital ones become grants."""
    ShopItem = apps.get_model("shop", "ShopItem")
    ShopItem.objects.filter(kind="shipped").update(kind="manual")
    ShopItem.objects.filter(kind="digital").update(kind="grant")


class Migration(migrations.Migration):

    dependencies = [
        ('shop', '0002_regions_and_rate_classes'),
    ]

    operations = [
        migrations.RunPython(kinds_to_grant_or_manual, migrations.RunPython.noop),
        migrations.RemoveConstraint(
            model_name='regionalprice',
            name='regionalprice_cookies_positive',
        ),
        migrations.RemoveConstraint(
            model_name='regionalprice',
            name='regionalprice_usd_positive',
        ),
        migrations.RemoveConstraint(
            model_name='regionalprice',
            name='regionalprice_override_positive',
        ),
        migrations.RemoveConstraint(
            model_name='regionalprice',
            name='one_price_per_item_and_region',
        ),
        migrations.RemoveField(
            model_name='shopitem',
            name='category',
        ),
        migrations.AlterField(
            model_name='rateclass',
            name='markup',
            field=models.DecimalField(decimal_places=3, help_text='Prices are stored when an item is saved: after changing this, run Recompute prices on the items.', max_digits=5, validators=[django.core.validators.MinValueValidator(Decimal('0.001'))]),
        ),
        migrations.AlterField(
            model_name='shopitem',
            name='base_item',
            field=models.ForeignKey(blank=True, help_text='Set this to make the item an UPGRADE of that base grant: it tops up the same card and is never sold alone.', limit_choices_to={'base_item__isnull': True}, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='upgrades', to='shop.shopitem'),
        ),
        migrations.AlterField(
            model_name='shopitem',
            name='kind',
            field=models.CharField(choices=[('grant', 'Card grant'), ('manual', 'By hand')], default='grant', help_text='Everything is a card grant unless it cannot be: those staff hand over themselves.', max_length=10),
        ),
        migrations.AlterField(
            model_name='shopitem',
            name='usd_value',
            field=models.DecimalField(decimal_places=2, help_text="A grant's value on the card. Shown to visitors for grants. For a by-hand item it is just our cost.", max_digits=8, validators=[django.core.validators.MinValueValidator(Decimal('0.01'))], verbose_name='dollar value'),
        ),
        migrations.RemoveField(
            model_name='regionalprice',
            name='item',
        ),
        migrations.RemoveField(
            model_name='regionalprice',
            name='region',
        ),
        migrations.DeleteModel(
            name='Region',
        ),
        migrations.DeleteModel(
            name='RegionalPrice',
        ),
    ]
