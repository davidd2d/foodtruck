from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('orders', '0014_order_dashboard_lifecycle'),
    ]

    operations = [
        migrations.AddField(
            model_name='order',
            name='paid_at',
            field=models.DateTimeField(blank=True, help_text='When the order was paid', null=True),
        ),
        migrations.AddIndex(
            model_name='order',
            index=models.Index(fields=['paid_at'], name='orders_orde_paid_at_70c075_idx'),
        ),
    ]
