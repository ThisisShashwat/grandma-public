"""Data migration: hardware projects with status building whose design submission is approved with claimed_at set
and that have no build submission become awaiting_build. Reverse is no-op."""
from django.db import migrations


def make_awaiting_build(apps, schema_editor):
    Project = apps.get_model("projects", "Project")
    Submission = apps.get_model("submissions", "Submission")
    for project in Project.objects.filter(status="building", category__kind="hardware"):
        has_approved_claimed_design = Submission.objects.filter(
            project=project,
            stage="design",
            status="approved",
            claimed_at__isnull=False,
        ).exists()
        has_build_submission = Submission.objects.filter(
            project=project,
            stage="build",
        ).exists()
        if has_approved_claimed_design and not has_build_submission:
            project.status = "awaiting_build"
            project.save(update_fields=["status"])


class Migration(migrations.Migration):

    dependencies = [
        ('submissions', '0003_prose_validators'),
        ('projects', '0005_one_working_project_per_user'),
    ]

    operations = [
        migrations.RunPython(make_awaiting_build, migrations.RunPython.noop),
    ]
