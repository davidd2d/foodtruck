from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('orders', '0018_order_anonymized_at_order_customer_email_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='order',
            name='payment_method',
            field=models.CharField(
                choices=[('online', 'Online payment'), ('on_site', 'Pay at the food truck')],
                default='online',
                help_text='How the customer intends to pay for the order',
                max_length=20,
            ),
        ),
    ]