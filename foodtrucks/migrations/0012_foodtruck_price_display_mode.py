from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('foodtrucks', '0011_foodtruck_stripe_charges_enabled_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='foodtruck',
            name='price_display_mode',
            field=models.CharField(
                choices=[
                    ('tax_excluded', 'Taxes added to displayed prices'),
                    ('tax_included', 'Taxes included in displayed prices'),
                ],
                default='tax_included',
                help_text='Whether displayed prices already include taxes or should show taxes separately',
                max_length=20,
            ),
        ),
    ]