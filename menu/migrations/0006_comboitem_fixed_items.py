from django.db import migrations, models


def copy_legacy_item_to_fixed_items(apps, schema_editor):
    ComboItem = apps.get_model('menu', 'ComboItem')
    through_model = ComboItem.fixed_items.through

    relations = [
        through_model(comboitem_id=combo_item_id, item_id=item_id)
        for combo_item_id, item_id in ComboItem.objects.exclude(item_id__isnull=True).values_list('id', 'item_id')
    ]
    if relations:
        through_model.objects.bulk_create(relations, ignore_conflicts=True)


def restore_legacy_item_from_fixed_items(apps, schema_editor):
    ComboItem = apps.get_model('menu', 'ComboItem')
    through_model = ComboItem.fixed_items.through

    first_fixed_by_combo = {}
    for comboitem_id, item_id in through_model.objects.order_by('id').values_list('comboitem_id', 'item_id'):
        first_fixed_by_combo.setdefault(comboitem_id, item_id)

    for combo_item in ComboItem.objects.all():
        combo_item.item_id = first_fixed_by_combo.get(combo_item.id)
        combo_item.save(update_fields=['item'])


class Migration(migrations.Migration):

    dependencies = [
        ('menu', '0005_combo_discount_and_component_category'),
    ]

    operations = [
        migrations.AddField(
            model_name='comboitem',
            name='fixed_items',
            field=models.ManyToManyField(blank=True, help_text='Fixed menu items always included for this combo component', related_name='fixed_combo_components', to='menu.item'),
        ),
        migrations.RunPython(copy_legacy_item_to_fixed_items, restore_legacy_item_from_fixed_items),
    ]
