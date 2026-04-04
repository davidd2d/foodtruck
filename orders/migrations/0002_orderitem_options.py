from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('orders', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='orderitem',
            name='options',
            field=models.JSONField(blank=True, default=list, help_text='Selected item options snapshot'),
        ),
    ]
