import accounts.public_id
from django.db import migrations, models


class Migration(migrations.Migration):
    """Step 3 of 3: the public id is required and unique, and every new profile gets a random one."""

    dependencies = [
        ('accounts', '0010_profile_public_id_fill'),
    ]

    operations = [
        migrations.AlterField(
            model_name='profile',
            name='public_id',
            field=models.CharField(default=accounts.public_id.new_public_id, editable=False, help_text="The random id in the person's public address (/u/<id>-<name>/), so the database number never shows. Made once, never changed.", max_length=10, unique=True),
        ),
    ]
