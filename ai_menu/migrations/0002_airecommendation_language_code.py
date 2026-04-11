from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ai_menu', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='airecommendation',
            name='language_code',
            field=models.CharField(
                choices=settings.LANGUAGES,
                default=settings.LANGUAGE_CODE,
                help_text='Language used to generate this recommendation',
                max_length=10,
            ),
        ),
    ]