import uuid
from decimal import Decimal
from django.utils import timezone
from datetime import timedelta
from foodtrucks.tests.factories import FoodTruckFactory
from menu.models import Menu, Category, Item, Combo, ComboItem, OptionGroup, Option


def MenuFactory(food_truck=None, name=None, is_active=True):
    food_truck = food_truck or FoodTruckFactory()
    return Menu.objects.create(
        food_truck=food_truck,
        name=name or f"Menu {uuid.uuid4().hex[:8]}",
        is_active=is_active,
    )


def CategoryFactory(menu=None, name='General', display_order=0):
    menu = menu or MenuFactory()
    return Category.objects.create(
        menu=menu,
        name=name,
        display_order=display_order,
    )


def ItemFactory(category=None, name='Item', description='Item description', base_price=Decimal('0.00'), is_available=True, display_order=0):
    category = category or CategoryFactory()
    return Item.objects.create(
        category=category,
        name=name,
        description=description,
        base_price=base_price,
        is_available=is_available,
        display_order=display_order,
    )


def ComboFactory(category=None, name='Combo', description='Combo description', combo_price=None, discount_amount=Decimal('0.00'), is_available=True, display_order=0, tax=None):
    category = category or CategoryFactory()
    return Combo.objects.create(
        category=category,
        name=name,
        description=description,
        tax=tax,
        combo_price=combo_price,
        discount_amount=discount_amount,
        is_available=is_available,
        display_order=display_order,
    )


def ComboItemFactory(combo=None, item=None, source_category=None, display_name='Combo Item', quantity=1, display_order=0):
    combo = combo or ComboFactory()
    if item is None and source_category is None:
        item = ItemFactory(category=combo.category, name=display_name)
    return ComboItem.objects.create(
        combo=combo,
        item=item,
        source_category=source_category,
        display_name=display_name,
        quantity=quantity,
        display_order=display_order,
    )


def OptionGroupFactory(item=None, name='Size', required=False, min_choices=0, max_choices=None):
    item = item or ItemFactory()
    return OptionGroup.objects.create(
        item=item,
        name=name,
        required=required,
        min_choices=min_choices,
        max_choices=max_choices,
    )


def OptionFactory(group=None, name='Option', price_modifier=Decimal('0.00'), is_available=True):
    group = group or OptionGroupFactory()
    return Option.objects.create(
        group=group,
        name=name,
        price_modifier=price_modifier,
        is_available=is_available,
    )
