import accounts.public_id
from django.db import migrations, models


class Migration(migrations.Migration):
    """Step 3 of 3: the public id is required and unique, and every new project gets a random one."""

    dependencies = [
        ('projects', '0014_project_public_id_fill'),
    ]

    operations = [
        migrations.AlterField(
            model_name='project',
            name='public_id',
            field=models.CharField(default=accounts.public_id.new_public_id, editable=False, help_text="The random id in the project's public address (/p/<id>-<name>/), so the database number never shows. Made once, never changed.", max_length=10, unique=True),
        ),
    ]
