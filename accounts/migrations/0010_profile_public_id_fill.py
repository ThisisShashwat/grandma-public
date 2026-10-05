from django.db import migrations

from accounts.public_id import new_public_id


def fill_public_ids(apps, schema_editor):
    """Step 2 of 3: every profile without a public id gets a random one. Each is 51 random bits, so two never meet in practice, and
    step 3 (unique) fails loudly if they ever did. Going back changes nothing: the column is dropped by step 1's reverse."""
    Profile = apps.get_model("accounts", "Profile")
    for profile in Profile.objects.filter(public_id__isnull=True):
        profile.public_id = new_public_id()
        profile.save(update_fields=["public_id"])


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0009_profile_public_id_add'),
    ]

    operations = [
        migrations.RunPython(fill_public_ids, migrations.RunPython.noop),
    ]
