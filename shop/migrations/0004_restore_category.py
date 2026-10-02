"""The owner wants the simple `category` field back (the page is grouped by it again). 0003 stays as it was: it was applied
and committed, so this migration adds the field again. Existing rows land on "fun"; the owner re-sorts them in the admin."""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('shop', '0003_all_grants_no_regions'),
    ]

    operations = [
        migrations.AddField(
            model_name='shopitem',
            name='category',
            field=models.CharField(choices=[('hardware', 'Hardware'), ('software', 'Software'), ('credits', 'Credits'), ('fun', 'Fun'), ('joke', 'Jokes')], default='fun', help_text='Which shelf of the page it sits on.', max_length=10),
            preserve_default=False,
        ),
    ]
