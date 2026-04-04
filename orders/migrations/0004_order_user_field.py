from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('orders', '0003_add_submission_fields'),
    ]

    operations = [
        migrations.RenameField(
            model_name='order',
            old_name='customer',
            new_name='user',
        ),
        migrations.AlterField(
            model_name='order',
            name='user',
            field=models.ForeignKey(
                blank=True,
                help_text='The account that placed or owns this order',
                null=True,
                on_delete=models.CASCADE,
                related_name='orders',
                to=settings.AUTH_USER_MODEL,
            ),
        ),
    ]
