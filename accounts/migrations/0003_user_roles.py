from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0002_user_email_verified'),
    ]

    operations = [
        migrations.AddField(
            model_name='user',
            name='is_foodtruck_owner',
            field=models.BooleanField(default=False, help_text='Whether the user owns or manages food trucks'),
        ),
        migrations.AddField(
            model_name='user',
            name='is_customer',
            field=models.BooleanField(default=True, help_text='Whether the user places orders'),
        ),
    ]
