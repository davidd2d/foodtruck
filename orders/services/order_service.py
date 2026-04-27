from decimal import Decimal
import logging

from django.core.exceptions import ValidationError
from django.db import transaction

from foodtrucks.models import FoodTruck
from menu.models import Combo, Item
from orders.models import Order, PickupSlot
from orders.exceptions import OrderTransitionError
from orders.services.cart_service import CartService


logger = logging.getLogger(__name__)


class OrderService:
    """Service layer responsible for orchestrating order workflows."""

    @staticmethod
    def create_order_from_cart(user, session, pickup_slot_id=None, payment_method=Order.PaymentMethod.ONLINE):
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

        if not food_truck.can_accept_orders():
            raise ValidationError('This foodtruck cannot accept orders.')

        with transaction.atomic():
            order = Order.objects.create(
                user=user,
                food_truck=food_truck,
                status=Order.Status.DRAFT,
                payment_method=payment_method,
                total_price=Decimal('0.00'),
            )

            for item_line in cart['items']:
                line_type = item_line.get('line_type', 'item')

                if line_type == 'combo':
                    combo = Combo.objects.select_related('category__menu__food_truck').get(id=item_line['combo_id'])

                    if combo.category.menu.food_truck.slug != cart['foodtruck_slug']:
                        raise ValidationError('Combo does not belong to the cart food truck.')

                    order.add_combo(
                        combo=combo,
                        quantity=item_line['quantity'],
                        combo_selections=item_line.get('combo_components', []),
                    )
                    continue

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
        if order.status != Order.Status.DRAFT:
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

    @staticmethod
    def update_status(order: Order, new_status: str) -> Order:
        """Atomically update an operator-facing order status using the domain rules."""
        try:
            normalized_status = new_status.lower()
        except AttributeError as exc:
            raise ValidationError('A valid status string is required.') from exc

        try:
            with transaction.atomic():
                locked_order = Order.objects.select_for_update().get(pk=order.pk)
                locked_order.transition_to(normalized_status)
                locked_order.save(update_fields=['status'])
                return locked_order
        except OrderTransitionError:
            logger.warning(
                'Invalid order transition',
                extra={
                    'order_id': order.pk,
                    'from_status': order.status,
                    'to_status': normalized_status,
                },
            )
            raise

    @staticmethod
    def get_dashboard_orders(foodtruck, filters: dict):
        """Return optimized orders for the owner dashboard with optional filters."""
        filters = filters or {}
        requested_status = filters.get('status')
        requested_slot = filters.get('slot')

        queryset = Order.objects.for_dashboard(
            foodtruck,
            include_cancelled=requested_status == Order.Status.CANCELLED,
        ).exclude(status=Order.Status.DRAFT)

        if requested_status:
            queryset = queryset.by_status(requested_status)

        if requested_slot:
            queryset = queryset.filter(pickup_slot_id=requested_slot)

        return queryset
