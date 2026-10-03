from django.db import migrations, models


def delete_hardware_orders(apps, schema_editor):
    Order = apps.get_model("orders", "Order")
    OrderPart = apps.get_model("orders", "OrderPart")
    OrderLine = apps.get_model("orders", "OrderLine")

    OrderPart.objects.all().delete()
    hardware_orders = Order.objects.filter(
        models.Q(project__isnull=False) | models.Q(item__needs_project=True)
    )
    OrderLine.objects.filter(order__in=hardware_orders).delete()
    hardware_orders.delete()


class Migration(migrations.Migration):
    dependencies = [
        ("orders", "0002_fulfillers_group"),
    ]

    operations = [
        migrations.RunPython(delete_hardware_orders, migrations.RunPython.noop),
    ]
