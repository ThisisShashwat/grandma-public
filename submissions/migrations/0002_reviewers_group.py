"""The "Reviewers" group: staff who may look at submissions and set an outcome, and nothing else. Add a person to it in the admin
(Users, Groups) and tick "Staff status". Permissions are normally made after all migrations have run, so this makes the ones it needs first."""
from django.contrib.auth.management import create_permissions
from django.db import migrations

NAME = "Reviewers"
PERMISSIONS = ("view_submission", "change_submission")


def make_group(apps, schema_editor):
    config = apps.get_app_config("submissions")
    config.models_module = True                               # create_permissions skips an app it thinks has no models
    create_permissions(config, apps=apps, verbosity=0)
    config.models_module = None
    group, _ = apps.get_model("auth", "Group").objects.get_or_create(name=NAME)
    group.permissions.set(apps.get_model("auth", "Permission").objects.filter(content_type__app_label="submissions", codename__in=PERMISSIONS))


class Migration(migrations.Migration):
    dependencies = [
        ("submissions", "0001_initial"),
        ("auth", "0012_alter_user_first_name_max_length"),
        ("contenttypes", "0002_remove_content_type_name"),
    ]
    operations = [migrations.RunPython(make_group, migrations.RunPython.noop)]       # rolling back must not delete a group staff have changed
