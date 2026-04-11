import uuid
from decimal import Decimal
from datetime import timedelta
from django.utils import timezone
from django.contrib.auth import get_user_model
from orders.models import Order, PickupSlot
from foodtrucks.tests.factories import FoodTruckFactory
from payments.models import Payment

User = get_user_model()


def UserFactory(email=None, password='password123'):
    return User.objects.create_user(
        email=email or f'user-{uuid.uuid4().hex[:8]}@example.com',
        password=password
    )


def OrderFactory(user=None, food_truck=None, pickup_slot=None, status='pending', total_price=Decimal('25.50')):
    user = user or UserFactory()
    food_truck = food_truck or FoodTruckFactory(owner=user)

    if pickup_slot is None:
        start_time = timezone.now() + timedelta(hours=1)
        end_time = start_time + timedelta(hours=1)
        pickup_slot = PickupSlot.objects.create(
            food_truck=food_truck,
            start_time=start_time,
            end_time=end_time,
            capacity=10
        )

    return Order.objects.create(
        user=user,
        food_truck=food_truck,
        pickup_slot=pickup_slot,
        status=status,
        total_price=total_price,
    )


def PaymentFactory(order=None, amount=None, status='pending', provider='stripe', currency='EUR'):
    order = order or OrderFactory()
    return Payment.objects.create(
        order=order,
        amount=amount or order.total_price,
        status=status,
        provider=provider,
        currency=currency
    )
