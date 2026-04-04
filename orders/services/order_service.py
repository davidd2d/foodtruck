from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction

from foodtrucks.models import FoodTruck
from menu.models import Item
from orders.models import Order, PickupSlot
from orders.services.cart_service import CartService


class OrderService:
    """Service layer responsible for orchestrating order finalization."""

    @staticmethod
    def create_order_from_cart(user, session, pickup_slot_id=None):
        """
        Construct an order from the session-backed cart and optionally assign a slot.
        """
        cart_service = CartService(session)
        cart = cart_service.get_cart()

        if not cart['items']:
            raise ValidationError('Cart is empty.')

        foodtruck_slug = cart.get('foodtruck_slug')
        if not foodtruck_slug:
            raise ValidationError('Cart must be associated with a food truck.')

        pickup_slot = None
        food_truck = None

        if pickup_slot_id:
            try:
                pickup_slot = PickupSlot.objects.select_related('food_truck').get(pk=pickup_slot_id)
            except PickupSlot.DoesNotExist:
                raise ValidationError('Pickup slot does not exist.')

            if cart['foodtruck_slug'] != pickup_slot.food_truck.slug:
                raise ValidationError('Pickup slot must belong to the selected food truck.')

            if not pickup_slot.is_available():
                raise ValidationError('Selected pickup slot is no longer available.')
            food_truck = pickup_slot.food_truck
        else:
            try:
                food_truck = FoodTruck.objects.get(slug=foodtruck_slug)
            except FoodTruck.DoesNotExist:
                raise ValidationError('Food truck does not exist.')

        with transaction.atomic():
            order = Order.objects.create(
                user=user,
                food_truck=food_truck,
                status='draft',
                total_price=Decimal('0.00'),
            )

            for item_line in cart['items']:
                item = Item.objects.select_related('category__menu__food_truck').get(id=item_line['item_id'])

                if item.category.menu.food_truck.slug != cart['foodtruck_slug']:
                    raise ValidationError('Item does not belong to the cart food truck.')

                item.validate_options([option['option_id'] for option in item_line.get('selected_options', [])])

                order.add_item(
                    item=item,
                    quantity=item_line['quantity'],
                    selected_options=[option['option_id'] for option in item_line.get('selected_options', [])],
                )

            if pickup_slot:
                pickup_slot.assign_order(order)

            cart_service.clear()

        return order

    @staticmethod
    def assign_pickup_slot(order, slot_id):
        """Assign a pickup slot to the provided draft order."""
        if order.status != 'draft':
            raise ValidationError('Only draft orders can be assigned a pickup slot.')

        try:
            slot = PickupSlot.objects.select_related('food_truck').get(pk=slot_id)
        except PickupSlot.DoesNotExist:
            raise ValidationError('Pickup slot does not exist.')

        if slot.food_truck_id != order.food_truck_id:
            raise ValidationError('Pickup slot belongs to another food truck.')

        return slot.assign_order(order)

    @staticmethod
    def submit_order(order):
        """Validate and submit a draft order."""
        return order.submit()
