import uuid
from datetime import timedelta
from decimal import Decimal
from django.contrib.auth import get_user_model
from django.utils import timezone
from common.models import Tax
from foodtrucks.models import FoodTruck, Plan, Subscription
from menu.models import Menu, Category, Combo, ComboItem, Item, OptionGroup, Option
from orders.models import PickupSlot, Order

User = get_user_model()


def _random_email():
    return f'user-{uuid.uuid4().hex[:8]}@example.com'


def UserFactory(email=None, password='password123'):
    return User.objects.create_user(
        email=email or _random_email(),
        password=password
    )


def PlanFactory(name='Pro Plan', code=None, price=Decimal('29.99'), allows_ordering=True):
    code = code or f'pro-{uuid.uuid4().hex[:6]}'
    plan, _ = Plan.objects.get_or_create(
        code=code,
        defaults={
            'name': name,
            'price': price,
            'allows_ordering': allows_ordering,
        }
    )
    return plan


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


def TaxFactory(name='TVA 10%', rate=Decimal('0.1000'), is_default=True):
    tax, _ = Tax.objects.get_or_create(
        name=name,
        defaults={'rate': rate, 'is_default': is_default},
    )
    if tax.rate != rate or tax.is_default != is_default:
        tax.rate = rate
        tax.is_default = is_default
        tax.save(update_fields=['rate', 'is_default'])
    return tax


def CategoryFactory(menu=None, name='Main'):
    menu = menu or MenuFactory()
    return Category.objects.create(menu=menu, name=name)


def ItemFactory(category=None, name='Margherita', description='Classic pizza', base_price=Decimal('12.00'), is_available=True, tax=None):
    category = category or CategoryFactory()
    tax = tax or TaxFactory()
    return Item.objects.create(
        category=category,
        name=name,
        description=description,
        tax=tax,
        base_price=base_price,
        is_available=is_available
    )


def ComboFactory(category=None, name='Lunch Combo', description='Combo', combo_price=Decimal('15.00'), is_available=True, display_order=0):
    category = category or CategoryFactory()
    return Combo.objects.create(
        category=category,
        name=name,
        description=description,
        combo_price=combo_price,
        is_available=is_available,
        display_order=display_order,
    )


def ComboItemFactory(combo=None, item=None, display_name='Combo Item', quantity=1, display_order=0):
    combo = combo or ComboFactory()
    item = item or ItemFactory(category=combo.category, name=display_name)
    return ComboItem.objects.create(
        combo=combo,
        item=item,
        display_name=display_name,
        quantity=quantity,
        display_order=display_order,
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


def PickupSlotFactory(food_truck=None, capacity=5, start_time=None, end_time=None, service_schedule=None):
    food_truck = food_truck or FoodTruckFactory()
    start_time = start_time or timezone.now() + timedelta(hours=1)
    end_time = end_time or (start_time + timedelta(hours=1))
    return PickupSlot.objects.create(
        food_truck=food_truck,
        start_time=start_time,
        end_time=end_time,
        capacity=capacity,
        service_schedule=service_schedule,
    )


def ServiceScheduleFactory(food_truck=None, day_of_week=0, start_time=None, end_time=None, capacity_per_slot=5, is_active=True):
    from orders.models import ServiceSchedule
    food_truck = food_truck or FoodTruckFactory()
    start_time = start_time or timezone.now().time().replace(hour=10, minute=0, second=0, microsecond=0)
    end_time = end_time or timezone.now().time().replace(hour=18, minute=0, second=0, microsecond=0)
    return ServiceSchedule.objects.create(
        food_truck=food_truck,
        day_of_week=day_of_week,
        start_time=start_time,
        end_time=end_time,
        capacity_per_slot=capacity_per_slot,
        is_active=is_active
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
