from decimal import Decimal

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('menu', '0004_combo_tax'),
    ]

    operations = [
        migrations.AddField(
            model_name='combo',
            name='discount_amount',
            field=models.DecimalField(decimal_places=2, default=Decimal('0.00'), help_text='Owner-defined reduction applied to the composed combo', max_digits=8),
        ),
        migrations.AddField(
            model_name='comboitem',
            name='source_category',
            field=models.ForeignKey(blank=True, help_text='Category from which the customer chooses the item for this combo component', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='combo_components', to='menu.category'),
        ),
    ]