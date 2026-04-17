import uuid

import django.db.models.deletion
from django.db import migrations, models
import django.utils.timezone


def populate_legacy_stripe_session_ids(apps, schema_editor):
    Payment = apps.get_model('payments', 'Payment')
    for payment in Payment.objects.filter(stripe_session_id__isnull=True).iterator():
        payment.stripe_session_id = f'legacy_{payment.pk}_{uuid.uuid4().hex[:16]}'
        payment.save(update_fields=['stripe_session_id'])


class Migration(migrations.Migration):

    dependencies = [
        ('payments', '0001_initial'),
        ('orders', '0015_order_paid_at'),
    ]

    operations = [
        migrations.AddField(
            model_name='payment',
            name='paid_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='payment',
            name='stripe_payment_intent',
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
        migrations.AddField(
            model_name='payment',
            name='stripe_session_id',
            field=models.CharField(blank=True, max_length=255, null=True, unique=True),
        ),
        migrations.AlterField(
            model_name='payment',
            name='order',
            field=models.OneToOneField(help_text='The order this payment is for', on_delete=django.db.models.deletion.PROTECT, related_name='payment', to='orders.order'),
        ),
        migrations.AlterField(
            model_name='payment',
            name='provider',
            field=models.CharField(default='stripe', help_text='Payment provider', max_length=32),
        ),
        migrations.AlterField(
            model_name='payment',
            name='status',
            field=models.CharField(choices=[('pending', 'Pending'), ('paid', 'Paid'), ('failed', 'Failed')], default='pending', help_text='Current payment status', max_length=20),
        ),
        migrations.RunPython(populate_legacy_stripe_session_ids, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='payment',
            name='stripe_session_id',
            field=models.CharField(max_length=255, unique=True),
        ),
        migrations.RemoveIndex(
            model_name='payment',
            name='payments_pa_provide_adf74c_idx',
        ),
        migrations.RemoveField(
            model_name='payment',
            name='currency',
        ),
        migrations.RemoveField(
            model_name='payment',
            name='provider_payment_id',
        ),
        migrations.AddIndex(
            model_name='payment',
            index=models.Index(fields=['paid_at'], name='payments_pa_paid_at_855e3d_idx'),
        ),
        migrations.CreateModel(
            name='StripeEvent',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('stripe_event_id', models.CharField(max_length=255, unique=True)),
                ('type', models.CharField(max_length=255)),
                ('processed_at', models.DateTimeField(default=django.utils.timezone.now)),
            ],
            options={
                'verbose_name': 'Stripe Event',
                'verbose_name_plural': 'Stripe Events',
                'ordering': ['-processed_at'],
            },
        ),
        migrations.AddIndex(
            model_name='stripeevent',
            index=models.Index(fields=['processed_at'], name='payments_st_processed_700e22_idx'),
        ),
    ]
