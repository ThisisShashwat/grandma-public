"""Data migration: delete hardware submissions (stage not empty, or category kind hardware). Reverse is no-op."""
from django.db import migrations, models


def delete_hardware_submissions(apps, schema_editor):
    Submission = apps.get_model("submissions", "Submission")
    Submission.objects.filter(
        (models.Q(stage__isnull=False) & ~models.Q(stage="")) | models.Q(project__category__kind="hardware")
    ).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("submissions", "0004_hardware_awaiting_build"),
    ]

    operations = [
        migrations.RunPython(delete_hardware_submissions, migrations.RunPython.noop),
    ]
