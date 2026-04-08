import uuid
from decimal import Decimal
from datetime import timedelta
from django.contrib.auth import get_user_model
from django.utils import timezone
from preferences.models import Preference
from foodtrucks.models import FoodTruck, Plan, Subscription
from menu.models import Menu, Category, Item, OptionGroup, Option
from orders.models import PickupSlot

User = get_user_model()


def _random_email():
    return f'user-{uuid.uuid4().hex[:8]}@example.com'


def UserFactory(email=None, password='password123', **kwargs):
    email = (email or _random_email()).strip().lower()
    if 'email_verified' not in kwargs:
        kwargs['email_verified'] = True

    user = User.objects.create_user(
        email=email,
        password=password
    )
    for attr, value in kwargs.items():
        setattr(user, attr, value)
    if kwargs:
        user.save()
    return user


def PreferenceFactory(name=None):
    return Preference.objects.create(
        name=name or f'Preference {uuid.uuid4().hex[:6]}'
    )


def PlanFactory(name='Standard Plan', code='pro', price=Decimal('29.99'), allows_ordering=True):
    plan, _ = Plan.objects.get_or_create(
        code=code,
        defaults={
            'name': name,
            'price': price,
            'allows_ordering': allows_ordering,
        }
    )
    return plan


def FoodTruckFactory(owner=None, name='Test Truck', description='Test description', latitude=40.7128, longitude=-74.0060, is_active=True):
    owner = owner or UserFactory()
    if not owner.is_foodtruck_owner:
        owner.is_foodtruck_owner = True
        owner.save(update_fields=['is_foodtruck_owner'])
    foodtruck = FoodTruck.objects.create(
        owner=owner,
        name=name,
        description=description,
        latitude=latitude,
        longitude=longitude,
        is_active=is_active
    )
    plan = PlanFactory()
    Subscription.objects.create(food_truck=foodtruck, plan=plan)
    return foodtruck


def MenuFactory(food_truck=None, name='Test Menu', is_active=True):
    food_truck = food_truck or FoodTruckFactory()
    return Menu.objects.create(
        food_truck=food_truck,
        name=name,
        is_active=is_active
    )


def CategoryFactory(menu=None, name='General', display_order=0):
    menu = menu or MenuFactory()
    return Category.objects.create(
        menu=menu,
        name=name,
        display_order=display_order
    )


def ItemFactory(category=None, name='Margherita', description='Classic pizza', base_price=Decimal('12.00'), is_available=True, display_order=0):
    category = category or CategoryFactory()
    item = Item.objects.create(
        category=category,
        name=name,
        description=description,
        base_price=base_price,
        is_available=is_available,
        display_order=display_order
    )
    return item


def OptionGroupFactory(item=None, name='Size', required=False, min_choices=0, max_choices=None):
    item = item or ItemFactory()
    return OptionGroup.objects.create(
        item=item,
        name=name,
        required=required,
        min_choices=min_choices,
        max_choices=max_choices
    )


def OptionFactory(group=None, name='Large', price_modifier=Decimal('2.00'), is_available=True):
    group = group or OptionGroupFactory()
    return Option.objects.create(
        group=group,
        name=name,
        price_modifier=price_modifier,
        is_available=is_available
    )


def PickupSlotFactory(food_truck=None, capacity=5, start_time=None, end_time=None):
    food_truck = food_truck or FoodTruckFactory()
    start_time = start_time or timezone.now() + timedelta(hours=1)
    end_time = end_time or (start_time + timedelta(hours=1))
    return PickupSlot.objects.create(
        food_truck=food_truck,
        start_time=start_time,
        end_time=end_time,
        capacity=capacity
    )
