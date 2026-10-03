from django.db import migrations


def delete_hardware_shop_items(apps, schema_editor):
    ShopItem = apps.get_model("shop", "ShopItem")

    ShopItem.objects.filter(base_item__needs_project=True).delete()
    ShopItem.objects.filter(needs_project=True).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("shop", "0005_needs_project"),
        ("orders", "0003_delete_hardware_orders"),
    ]

    operations = [
        migrations.RunPython(delete_hardware_shop_items, migrations.RunPython.noop),
    ]
