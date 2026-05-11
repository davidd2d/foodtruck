from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('foodtrucks', '0013_locationscore'),
    ]

    operations = [
        migrations.AddField(
            model_name='foodtruck',
            name='billing_address_line_1',
            field=models.CharField(blank=True, default='', help_text='Official billing street address', max_length=255),
        ),
        migrations.AddField(
            model_name='foodtruck',
            name='billing_address_line_2',
            field=models.CharField(blank=True, default='', help_text='Official billing address complement', max_length=255),
        ),
        migrations.AddField(
            model_name='foodtruck',
            name='billing_city',
            field=models.CharField(blank=True, default='', help_text='Official billing city', max_length=100),
        ),
        migrations.AddField(
            model_name='foodtruck',
            name='billing_country',
            field=models.CharField(blank=True, default='', help_text='Official billing country', max_length=100),
        ),
        migrations.AddField(
            model_name='foodtruck',
            name='billing_postal_code',
            field=models.CharField(blank=True, default='', help_text='Official billing postal code', max_length=20),
        ),
        migrations.AddField(
            model_name='foodtruck',
            name='billing_siret',
            field=models.CharField(blank=True, default='', help_text='French SIRET number used for billing', max_length=14),
        ),
        migrations.AddField(
            model_name='foodtruck',
            name='billing_vat_number',
            field=models.CharField(blank=True, default='', help_text='VAT number used on invoices when applicable', max_length=32),
        ),
        migrations.AddField(
            model_name='foodtruck',
            name='legal_business_name',
            field=models.CharField(blank=True, default='', help_text='Official business name used on invoices', max_length=255),
        ),
        migrations.AddField(
            model_name='foodtruck',
            name='service_address_line_1',
            field=models.CharField(blank=True, default='', help_text='Base service street address', max_length=255),
        ),
        migrations.AddField(
            model_name='foodtruck',
            name='service_address_line_2',
            field=models.CharField(blank=True, default='', help_text='Base service address complement', max_length=255),
        ),
        migrations.AddField(
            model_name='foodtruck',
            name='service_city',
            field=models.CharField(blank=True, default='', help_text='Base service city', max_length=100),
        ),
        migrations.AddField(
            model_name='foodtruck',
            name='service_country',
            field=models.CharField(blank=True, default='', help_text='Base service country', max_length=100),
        ),
        migrations.AddField(
            model_name='foodtruck',
            name='service_postal_code',
            field=models.CharField(blank=True, default='', help_text='Base service postal code', max_length=20),
        ),
    ]
