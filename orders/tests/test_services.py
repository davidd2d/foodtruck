from decimal import Decimal
from datetime import timedelta

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone
from orders.models import Order
from orders.services.cart_service import CartService
from orders.services.order_service import OrderService
from orders.tests.factories import (
    UserFactory,
    FoodTruckFactory,
    MenuFactory,
    CategoryFactory,
    ComboFactory,
    ComboItemFactory,
    ItemFactory,
    OptionGroupFactory,
    OptionFactory,
    PickupSlotFactory,
    OrderFactory,
)

from foodtrucks.tests.factories import PlanFactory


class DummySession(dict):
    """Thin session replacement for CartService tests."""

    def __init__(self):
        super().__init__()
        self.modified = False


class CartServiceTests(TestCase):
    def setUp(self):
        self.user = UserFactory()
        self.foodtruck = FoodTruckFactory(owner=self.user)
        self.menu = MenuFactory(food_truck=self.foodtruck)
        self.category = CategoryFactory(menu=self.menu)
        self.item = ItemFactory(category=self.category, base_price=Decimal('10.00'))
        self.combo = ComboFactory(category=self.category, combo_price=Decimal('14.00'))
        ComboItemFactory(combo=self.combo, item=self.item, display_name=self.item.name)
        self.session = self.client.session
        self.session.save()
        self.cart_service = CartService(self.session)

    def test_add_item_adds_to_session_cart(self):
        option_group = OptionGroupFactory(item=self.item, min_choices=0, max_choices=2)
        option = OptionFactory(group=option_group, price_modifier=Decimal('2.50'))

        self.cart_service.add_item(
            foodtruck_slug=self.foodtruck.slug,
            item_id=self.item.id,
            quantity=2,
            selected_options=[option.id],
        )

        cart = self.cart_service.get_cart()
        self.assertEqual(cart['item_count'], 2)
        self.assertEqual(cart['total_price'], '25.00')
        self.assertEqual(cart['items'][0]['item_name'], self.item.name)
        self.assertEqual(cart['items'][0]['selected_options'][0]['option_id'], option.id)

    def test_prevent_cross_foodtruck_items(self):
        other_truck = FoodTruckFactory()

        with self.assertRaises(ValidationError):
            self.cart_service.add_item(
                foodtruck_slug=other_truck.slug,
                item_id=self.item.id,
                quantity=1,
            )

    def test_get_total_reflects_options_and_quantities(self):
        option_group = OptionGroupFactory(item=self.item, min_choices=0, max_choices=2)
        option = OptionFactory(group=option_group, price_modifier=Decimal('1.50'))

        self.cart_service.add_item(
            foodtruck_slug=self.foodtruck.slug,
            item_id=self.item.id,
            quantity=3,
            selected_options=[option.id],
        )

        self.assertEqual(self.cart_service.get_total(), Decimal('34.50'))

    def test_remove_item_clears_selected_line(self):
        option_group = OptionGroupFactory(item=self.item, min_choices=0, max_choices=2)
        option = OptionFactory(group=option_group, price_modifier=Decimal('1.25'))

        self.cart_service.add_item(
            foodtruck_slug=self.foodtruck.slug,
            item_id=self.item.id,
            quantity=1,
            selected_options=[option.id],
        )
        line_key = self.cart_service.get_cart()['items'][0]['line_key']

        self.cart_service.remove_item(line_key)
        cart = self.cart_service.get_cart()

        self.assertEqual(cart['item_count'], 0)
        self.assertEqual(cart['total_price'], '0.00')

    def test_update_item_quantity_updates_total(self):
        self.cart_service.add_item(
            foodtruck_slug=self.foodtruck.slug,
            item_id=self.item.id,
            quantity=1,
        )

        line_key = self.cart_service.get_cart()['items'][0]['line_key']
        self.cart_service.update_item_quantity(line_key, 3)

        cart = self.cart_service.get_cart()
        self.assertEqual(cart['item_count'], 3)
        self.assertEqual(cart['items'][0]['quantity'], 3)
        self.assertEqual(cart['total_price'], '30.00')

    def test_add_combo_adds_to_session_cart(self):
        self.cart_service.add_combo(
            foodtruck_slug=self.foodtruck.slug,
            combo_id=self.combo.id,
            quantity=2,
        )

        cart = self.cart_service.get_cart()
        self.assertEqual(cart['item_count'], 2)
        self.assertEqual(cart['items'][0]['line_type'], 'combo')
        self.assertEqual(cart['items'][0]['combo_id'], self.combo.id)
        self.assertEqual(cart['total_price'], '28.00')

    def test_add_configurable_combo_adds_selected_components_and_discounted_total(self):
        dessert_category = CategoryFactory(menu=self.category.menu, name='Desserts')
        dessert = ItemFactory(category=dessert_category, name='Tiramisu', base_price=Decimal('4.00'))
        option_group = OptionGroupFactory(item=self.item, name='Extras', min_choices=0, max_choices=2)
        option = OptionFactory(group=option_group, name='Cheese', price_modifier=Decimal('1.50'))
        configurable_combo = ComboFactory(category=self.category, combo_price=None, discount_amount=Decimal('2.00'))
        ComboItemFactory(combo=configurable_combo, source_category=self.category, item=None, display_name='Main')
        ComboItemFactory(combo=configurable_combo, source_category=dessert_category, item=None, display_name='Dessert')

        self.cart_service.add_combo(
            foodtruck_slug=self.foodtruck.slug,
            combo_id=configurable_combo.id,
            quantity=1,
            combo_selections=[
                {'combo_item_id': configurable_combo.combo_items.order_by('id')[0].id, 'item_id': self.item.id, 'selected_options': [option.id]},
                {'combo_item_id': configurable_combo.combo_items.order_by('id')[1].id, 'item_id': dessert.id, 'selected_options': []},
            ],
        )

        cart = self.cart_service.get_cart()
        self.assertEqual(cart['items'][0]['line_type'], 'combo')
        self.assertEqual(cart['items'][0]['total_price'], '13.50')
        self.assertEqual(len(cart['items'][0]['combo_components']), 2)
        self.assertEqual(cart['items'][0]['combo_components'][0]['selected_options'][0]['name'], 'Cheese')


class OrderServiceTests(TestCase):
    def setUp(self):
        self.user = UserFactory()
        self.foodtruck = FoodTruckFactory(owner=self.user)
        self.slot = PickupSlotFactory(food_truck=self.foodtruck, capacity=2)
        self.category = CategoryFactory(menu=MenuFactory(food_truck=self.foodtruck), name='Pizza')
        self.item = ItemFactory(category=self.category, base_price=Decimal('11.00'))
        self.combo = ComboFactory(category=self.category, combo_price=Decimal('16.00'))
        ComboItemFactory(combo=self.combo, item=self.item, display_name=self.item.name)
        pro_plan = PlanFactory(code='pro', allows_ordering=True)
        subscription = self.foodtruck.subscription
        subscription.plan = pro_plan
        subscription.status = 'active'
        subscription.end_date = timezone.now() + timedelta(days=30)
        subscription.save(update_fields=['plan', 'status', 'end_date'])

    def test_assign_pickup_slot_with_matching_truck(self):
        order = OrderFactory(user=self.user, food_truck=self.foodtruck, pickup_slot=None)

        OrderService.assign_pickup_slot(order, self.slot.id)

        order.refresh_from_db()
        self.assertEqual(order.pickup_slot_id, self.slot.id)

    def test_assign_pickup_slot_rejects_different_truck(self):
        different_truck = FoodTruckFactory()
        order = OrderFactory(user=self.user, food_truck=different_truck, pickup_slot=None)

        with self.assertRaises(ValidationError):
            OrderService.assign_pickup_slot(order, self.slot.id)

    def test_submit_order_marks_submitted(self):
        order = OrderFactory(user=self.user, food_truck=self.foodtruck, pickup_slot=self.slot)
        order.add_item(self.item, quantity=1)

        OrderService.submit_order(order)

        order.refresh_from_db()
        self.assertEqual(order.status, 'pending')
        self.assertIsNotNone(order.submitted_at)

    def test_create_order_from_cart_persists_payment_method(self):
        session = self.client.session
        session.save()
        cart_service = CartService(session)
        cart_service.add_item(
            foodtruck_slug=self.foodtruck.slug,
            item_id=self.item.id,
            quantity=1,
        )

        order = OrderService.create_order_from_cart(
            user=self.user,
            session=session,
            payment_method=Order.PaymentMethod.ON_SITE,
        )

        self.assertEqual(order.payment_method, Order.PaymentMethod.ON_SITE)

    def test_submit_order_rolls_back_when_slot_full(self):
        slot = PickupSlotFactory(food_truck=self.foodtruck, capacity=1)
        first = OrderFactory(user=self.user, food_truck=self.foodtruck, pickup_slot=slot)
        first.add_item(self.item, quantity=1)
        first.submit()

        second = OrderFactory(user=self.user, food_truck=self.foodtruck, pickup_slot=slot)
        second.add_item(self.item, quantity=1)

        with self.assertRaises(ValidationError):
            OrderService.submit_order(second)

        second.refresh_from_db()
        self.assertEqual(second.status, 'draft')

    def test_update_status_applies_valid_transition(self):
        order = OrderFactory(user=self.user, food_truck=self.foodtruck, pickup_slot=self.slot)
        order.add_item(self.item, quantity=1)
        order.submit()

        updated = OrderService.update_status(order, 'confirmed')

        self.assertEqual(updated.status, 'confirmed')

    def test_get_dashboard_orders_excludes_drafts(self):
        draft_order = OrderFactory(user=self.user, food_truck=self.foodtruck, pickup_slot=self.slot, status='draft')
        pending_order = OrderFactory(user=self.user, food_truck=self.foodtruck, pickup_slot=self.slot, status='draft')
        pending_order.add_item(self.item, quantity=1)
        pending_order.submit()

        orders = list(OrderService.get_dashboard_orders(self.foodtruck, {}))

        self.assertNotIn(draft_order, orders)
        self.assertIn(pending_order, orders)

    def test_create_order_rejects_foodtruck_without_pro_subscription(self):
        free_truck = FoodTruckFactory(owner=self.user, name='Free Truck')
        free_truck.subscription.status = 'inactive'
        free_truck.subscription.save(update_fields=['status'])

        free_menu = MenuFactory(food_truck=free_truck)
        free_category = CategoryFactory(menu=free_menu)
        free_item = ItemFactory(category=free_category, base_price=Decimal('1.00'))

        session = DummySession()
        session[CartService.SESSION_KEY] = {
            'foodtruck_slug': free_truck.slug,
            'items': [
                {
                    'line_key': '1',
                    'item_id': free_item.id,
                    'item_name': free_item.name,
                    'quantity': 1,
                    'unit_price': '1.00',
                    'total_price': '1.00',
                    'selected_options': [],
                }
            ],
        }

        with self.assertRaises(ValidationError):
            OrderService.create_order_from_cart(self.user, session)

    def test_create_order_from_cart_with_combo(self):
        session = DummySession()
        session[CartService.SESSION_KEY] = {
            'foodtruck_slug': self.foodtruck.slug,
            'items': [
                {
                    'line_key': f'combo:{self.combo.id}:',
                    'line_type': 'combo',
                    'item_id': None,
                    'combo_id': self.combo.id,
                    'item_name': self.combo.name,
                    'quantity': 1,
                    'unit_price': '16.00',
                    'total_price': '16.00',
                    'selected_options': [],
                }
            ],
        }

        order = OrderService.create_order_from_cart(self.user, session, pickup_slot_id=self.slot.id)

        self.assertEqual(order.items.count(), 1)
        self.assertEqual(order.items.first().combo_id, self.combo.id)
        self.assertEqual(order.total_price, Decimal('17.60'))

    def test_create_order_from_cart_with_configurable_combo_keeps_snapshot(self):
        dessert_category = CategoryFactory(menu=self.category.menu, name='Desserts')
        dessert = ItemFactory(category=dessert_category, name='Cookie', base_price=Decimal('3.00'))
        option_group = OptionGroupFactory(item=self.item, name='Extras', min_choices=0, max_choices=2)
        option = OptionFactory(group=option_group, name='Cheese', price_modifier=Decimal('1.00'))
        configurable_combo = ComboFactory(category=self.category, combo_price=None, discount_amount=Decimal('2.00'))
        main_component = ComboItemFactory(combo=configurable_combo, source_category=self.category, item=None, display_name='Main')
        dessert_component = ComboItemFactory(combo=configurable_combo, source_category=dessert_category, item=None, display_name='Dessert')

        session = DummySession()
        session[CartService.SESSION_KEY] = {
            'foodtruck_slug': self.foodtruck.slug,
            'items': [
                {
                    'line_key': f'combo:{configurable_combo.id}:snapshot',
                    'line_type': 'combo',
                    'item_id': None,
                    'combo_id': configurable_combo.id,
                    'item_name': configurable_combo.name,
                    'component_summary': 'Margherita, Cookie',
                    'quantity': 1,
                    'unit_price': '12.00',
                    'total_price': '12.00',
                    'combo_components': [
                        {
                            'combo_item_id': main_component.id,
                            'item_id': self.item.id,
                            'selected_options': [{'option_id': option.id}],
                        },
                        {
                            'combo_item_id': dessert_component.id,
                            'item_id': dessert.id,
                            'selected_options': [],
                        },
                    ],
                    'selected_options': [],
                }
            ],
        }

        order = OrderService.create_order_from_cart(self.user, session, pickup_slot_id=self.slot.id)

        self.assertEqual(order.items.count(), 1)
        self.assertEqual(order.items.first().combo_id, configurable_combo.id)
        self.assertEqual(len(order.items.first().options), 2)
