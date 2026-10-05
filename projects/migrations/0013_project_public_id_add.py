from django.db import migrations, models


class Migration(migrations.Migration):
    """Step 1 of 3 for the random public id (Q33): the column, empty for now. Step 2 fills it, step 3 makes it required and unique."""

    dependencies = [
        ('projects', '0012_complaint'),
    ]

    operations = [
        migrations.AddField(
            model_name='project',
            name='public_id',
            field=models.CharField(editable=False, max_length=10, null=True),
        ),
    ]
