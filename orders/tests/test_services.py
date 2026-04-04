from decimal import Decimal
from django.core.exceptions import ValidationError
from django.test import TestCase
from orders.services.cart_service import CartService
from orders.services.order_service import OrderService
from orders.tests.factories import (
    UserFactory,
    FoodTruckFactory,
    MenuFactory,
    CategoryFactory,
    ItemFactory,
    OptionGroupFactory,
    OptionFactory,
    PickupSlotFactory,
    OrderFactory,
)


class CartServiceTests(TestCase):
    def setUp(self):
        self.user = UserFactory()
        self.foodtruck = FoodTruckFactory(owner=self.user)
        self.menu = MenuFactory(food_truck=self.foodtruck)
        self.category = CategoryFactory(menu=self.menu)
        self.item = ItemFactory(category=self.category, base_price=Decimal('10.00'))
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


class OrderServiceTests(TestCase):
    def setUp(self):
        self.user = UserFactory()
        self.foodtruck = FoodTruckFactory(owner=self.user)
        self.slot = PickupSlotFactory(food_truck=self.foodtruck, capacity=2)
        self.category = CategoryFactory(menu=MenuFactory(food_truck=self.foodtruck), name='Pizza')
        self.item = ItemFactory(category=self.category, base_price=Decimal('11.00'))

    def test_assign_pickup_slot_with_matching_truck(self):
        order = OrderFactory(customer=self.user, food_truck=self.foodtruck, pickup_slot=None)

        OrderService.assign_pickup_slot(order, self.slot.id)

        order.refresh_from_db()
        self.assertEqual(order.pickup_slot_id, self.slot.id)

    def test_assign_pickup_slot_rejects_different_truck(self):
        different_truck = FoodTruckFactory()
        order = OrderFactory(customer=self.user, food_truck=different_truck, pickup_slot=None)

        with self.assertRaises(ValidationError):
            OrderService.assign_pickup_slot(order, self.slot.id)

    def test_submit_order_marks_submitted(self):
        order = OrderFactory(customer=self.user, food_truck=self.foodtruck, pickup_slot=self.slot)
        order.add_item(self.item, quantity=1)

        OrderService.submit_order(order)

        order.refresh_from_db()
        self.assertEqual(order.status, 'submitted')
        self.assertIsNotNone(order.submitted_at)

    def test_submit_order_rolls_back_when_slot_full(self):
        slot = PickupSlotFactory(food_truck=self.foodtruck, capacity=1)
        first = OrderFactory(customer=self.user, food_truck=self.foodtruck, pickup_slot=slot)
        first.add_item(self.item, quantity=1)
        first.submit()

        second = OrderFactory(customer=self.user, food_truck=self.foodtruck, pickup_slot=slot)
        second.add_item(self.item, quantity=1)

        with self.assertRaises(ValidationError):
            OrderService.submit_order(second)

        second.refresh_from_db()
        self.assertEqual(second.status, 'draft')
