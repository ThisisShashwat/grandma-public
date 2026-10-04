import re
from django.db import migrations

TABLES = {"order": "orders_order", "submission": "submissions_submission", "redeal": "projects_project"}
KEY = re.compile(r"^(order|submission|redeal)[:-](\d+)")


def lift(apps, schema_editor):
    """SQLite resets its id counters when it rebuilds a table: lift each one above every id a ledger key still names."""
    if schema_editor.connection.vendor != "sqlite":
        return
    highest = {}
    with schema_editor.connection.cursor() as cursor:
        cursor.execute("select key from ledger_cookieentry")
        for (key,) in cursor.fetchall():
            if m := KEY.match(key):
                highest[m[1]] = max(highest.get(m[1], 0), int(m[2]))
        for kind, n in highest.items():
            cursor.execute("update sqlite_sequence set seq = max(seq, %s) where name = %s", [n, TABLES[kind]])


class Migration(migrations.Migration):
    dependencies = [
        ("ledger", "0001_initial"),
        ("orders", "0004_remove_orderpart_and_project"),
        ("submissions", "0008_hackatime_hours"),
        ("projects", "0010_hackatime_hours"),
    ]
    operations = [migrations.RunPython(lift, migrations.RunPython.noop)]
