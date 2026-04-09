from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('orders', '0006_serviceschedule_pickupslot_service_schedule'),
    ]

    operations = [
        migrations.AddConstraint(
            model_name='serviceschedule',
            constraint=models.UniqueConstraint(
                fields=['food_truck', 'day_of_week', 'start_time', 'end_time'],
                name='orders_unique_service_schedule_window'
            ),
        ),
    ]
