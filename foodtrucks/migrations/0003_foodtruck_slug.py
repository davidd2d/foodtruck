from django.db import migrations, models
from django.utils.text import slugify


def generate_unique_slugs(apps, schema_editor):
    FoodTruck = apps.get_model('foodtrucks', 'FoodTruck')

    for truck in FoodTruck.objects.all():
        base_slug = slugify(truck.name) or 'foodtruck'
        slug = base_slug
        index = 1
        while FoodTruck.objects.filter(slug=slug).exclude(pk=truck.pk).exists():
            slug = f"{base_slug}-{index}"
            index += 1
        truck.slug = slug
        truck.save(update_fields=['slug'])


class Migration(migrations.Migration):
    dependencies = [
        ('foodtrucks', '0002_plan_subscription'),
    ]

    operations = [
        migrations.AddField(
            model_name='foodtruck',
            name='slug',
            field=models.SlugField(blank=True, db_index=False, help_text='SEO-friendly resource slug', max_length=255, null=True),
        ),
        migrations.RunPython(generate_unique_slugs, reverse_code=migrations.RunPython.noop),
        migrations.AlterField(
            model_name='foodtruck',
            name='slug',
            field=models.SlugField(blank=True, db_index=False, help_text='SEO-friendly resource slug', max_length=255, unique=True, null=False),
        ),
    ]
