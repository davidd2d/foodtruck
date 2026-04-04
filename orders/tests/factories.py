import uuid
from datetime import timedelta
from decimal import Decimal
from django.contrib.auth import get_user_model
from django.utils import timezone
from foodtrucks.models import FoodTruck, Plan, Subscription
from menu.models import Menu, Category, Item, OptionGroup, Option
from orders.models import PickupSlot, Order

User = get_user_model()


def _random_email():
    return f'user-{uuid.uuid4().hex[:8]}@example.com'


def UserFactory(email=None, password='password123'):
    return User.objects.create_user(
        email=email or _random_email(),
        password=password
    )


def PlanFactory(name='Standard Plan', code=None, price=Decimal('29.99'), allows_ordering=True):
    code = code or f'standard-{uuid.uuid4().hex[:8]}'
    return Plan.objects.create(
        name=name,
        code=code,
        price=price,
        allows_ordering=allows_ordering
    )


def FoodTruckFactory(owner=None, name='Test Truck', description='Test description', latitude=40.7128, longitude=-74.0060):
    owner = owner or UserFactory()
    foodtruck = FoodTruck.objects.create(
        owner=owner,
        name=name,
        description=description,
        latitude=latitude,
        longitude=longitude
    )
    plan = PlanFactory()
    Subscription.objects.create(food_truck=foodtruck, plan=plan)
    return foodtruck


def MenuFactory(food_truck=None, name='Test Menu'):
    food_truck = food_truck or FoodTruckFactory()
    return Menu.objects.create(food_truck=food_truck, name=name)


def CategoryFactory(menu=None, name='Main'):
    menu = menu or MenuFactory()
    return Category.objects.create(menu=menu, name=name)


def ItemFactory(category=None, name='Margherita', description='Classic pizza', base_price=Decimal('12.00'), is_available=True):
    category = category or CategoryFactory()
    return Item.objects.create(
        category=category,
        name=name,
        description=description,
        base_price=base_price,
        is_available=is_available
    )


def OptionGroupFactory(item=None, name='Extras', min_choices=0, max_choices=None):
    item = item or ItemFactory()
    return OptionGroup.objects.create(
        item=item,
        name=name,
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


def OrderFactory(user=None, food_truck=None, pickup_slot=None, status='draft'):
    user = user or UserFactory()
    food_truck = food_truck or FoodTruckFactory(owner=user)
    pickup_slot = pickup_slot or PickupSlotFactory(food_truck=food_truck)
    return Order.objects.create(
        user=user,
        food_truck=food_truck,
        pickup_slot=pickup_slot,
        status=status
    )
