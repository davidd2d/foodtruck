from django.db import migrations, models
import django.db.models.deletion


def forwards_migrate_option_groups(apps, schema_editor):
    OptionGroup = apps.get_model('menu', 'OptionGroup')
    Option = apps.get_model('menu', 'Option')

    for group in OptionGroup.objects.select_related('item__category').prefetch_related('shared_items', 'options'):
        group.category_id = group.item.category_id
        group.save(update_fields=['category'])

        assigned_item_ids = {group.item_id}
        assigned_item_ids.update(group.shared_items.values_list('id', flat=True))

        if not assigned_item_ids:
            continue

        for option in group.options.all():
            option.items.add(*assigned_item_ids)


def backwards_migrate_option_groups(apps, schema_editor):
    OptionGroup = apps.get_model('menu', 'OptionGroup')

    for group in OptionGroup.objects.select_related('category').prefetch_related('options__items'):
        fallback_item_id = None
        for option in group.options.all():
            first_item = option.items.order_by('id').first()
            if first_item is not None:
                fallback_item_id = first_item.id
                break

        if fallback_item_id is None:
            fallback_item_id = group.category.items.order_by('id').values_list('id', flat=True).first()

        group.item_id = fallback_item_id
        group.save(update_fields=['item'])


class Migration(migrations.Migration):

    dependencies = [
        ('menu', '0008_optiongroupitem_optiongroup_shared_items_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='optiongroup',
            name='category',
            field=models.ForeignKey(
                blank=True,
                null=True,
                help_text='The category this option group belongs to',
                on_delete=django.db.models.deletion.CASCADE,
                related_name='option_groups',
                to='menu.category',
            ),
        ),
        migrations.AddField(
            model_name='option',
            name='items',
            field=models.ManyToManyField(
                blank=True,
                help_text='Items that can use this option',
                related_name='available_options',
                to='menu.item',
            ),
        ),
        migrations.RunPython(forwards_migrate_option_groups, backwards_migrate_option_groups),
        migrations.RemoveField(
            model_name='optiongroup',
            name='shared_items',
        ),
        migrations.RemoveField(
            model_name='optiongroup',
            name='item',
        ),
        migrations.DeleteModel(
            name='OptionGroupItem',
        ),
        migrations.AlterField(
            model_name='optiongroup',
            name='category',
            field=models.ForeignKey(
                help_text='The category this option group belongs to',
                on_delete=django.db.models.deletion.CASCADE,
                related_name='option_groups',
                to='menu.category',
            ),
        ),
    ]
