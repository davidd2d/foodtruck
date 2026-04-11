from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('foodtrucks', '0004_alter_foodtruck_slug'),
    ]

    operations = [
        migrations.AddField(
            model_name='foodtruck',
            name='default_language',
            field=models.CharField(
                choices=settings.LANGUAGES,
                default=settings.LANGUAGE_CODE,
                help_text='Primary content language for this food truck and its menu',
                max_length=10,
            ),
        ),
    ]