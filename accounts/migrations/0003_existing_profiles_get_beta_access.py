from django.conf import settings
from django.db import migrations


def give_everyone_access(apps, schema_editor):
    """Deploying the beta gate must not lock out the people already here: every existing profile gets beta access, and so does
    every account that has not met the site yet (its profile is only made the first time anything asks). Profiles made later start without it."""
    Profile = apps.get_model("accounts", "Profile")
    User = apps.get_model(*settings.AUTH_USER_MODEL.split("."))
    Profile.objects.update(beta_access=True)
    Profile.objects.bulk_create(Profile(user=user, beta_access=True) for user in User.objects.filter(profile__isnull=True))


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0002_profile_beta_access'),
    ]

    operations = [
        migrations.RunPython(give_everyone_access, migrations.RunPython.noop),
    ]
