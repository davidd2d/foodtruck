import threading
from decimal import Decimal
from datetime import timedelta, time
import math

from django.db import connections
from django.test import TestCase, TransactionTestCase
from django.core.exceptions import ValidationError
from django.utils import timezone

from orders.models import Order, PickupSlot, ServiceSchedule, Location, PARIS_TZ
from orders.services.schedule_service import generate_slots_for_date
from .factories import (
    UserFactory,
    ComboFactory,
    ComboItemFactory,
    FoodTruckFactory,
    ItemFactory,
    PickupSlotFactory,
    OrderFactory,
    OptionGroupFactory,
    OptionFactory,
    CategoryFactory,
    MenuFactory,
)


class OrderModelTests(TestCase):
    def setUp(self):
        self.user = UserFactory()
        self.foodtruck = FoodTruckFactory(owner=self.user)
        self.pickup_slot = PickupSlotFactory(food_truck=self.foodtruck, capacity=2)
        self.category = CategoryFactory(menu=MenuFactory(food_truck=self.foodtruck), name='Pizza')
        self.item = ItemFactory(category=self.category, base_price=Decimal('12.00'))
        self.combo = ComboFactory(category=self.category, combo_price=Decimal('18.00'))
        ComboItemFactory(combo=self.combo, item=self.item, display_name=self.item.name)

    def test_add_item_adds_order_item_and_updates_total(self):
        order = OrderFactory(user=self.user, food_truck=self.foodtruck, pickup_slot=self.pickup_slot)

        order.add_item(self.item, quantity=2)

        self.assertEqual(order.items.count(), 1)
        self.assertEqual(order.total_price, Decimal('24.00'))
        order_item = order.items.first()
        self.assertEqual(order_item.unit_price, Decimal('12.00'))
        self.assertEqual(order_item.total_price, Decimal('24.00'))

    def test_add_item_rejects_invalid_option_ids(self):
        order = OrderFactory(user=self.user, food_truck=self.foodtruck, pickup_slot=self.pickup_slot)

        with self.assertRaises(ValidationError):
            order.add_item(self.item, quantity=1, selected_options=[9999])

    def test_add_item_rejects_unavailable_item(self):
        unavailable_item = ItemFactory(category=self.category, is_available=False)
        order = OrderFactory(user=self.user, food_truck=self.foodtruck, pickup_slot=self.pickup_slot)

        with self.assertRaises(ValidationError):
            order.add_item(unavailable_item, quantity=1)

    def test_calculate_total_sums_multiple_items(self):
        order = OrderFactory(user=self.user, food_truck=self.foodtruck, pickup_slot=self.pickup_slot)
        order.add_item(self.item, quantity=1)
        order.add_item(self.item, quantity=2)

        self.assertEqual(order.calculate_total(), Decimal('36.00'))
        self.assertEqual(order.total_price, Decimal('36.00'))

    def test_can_be_submitted_false_when_no_items(self):
        order = OrderFactory(user=self.user, food_truck=self.foodtruck, pickup_slot=self.pickup_slot)
        self.assertFalse(order.can_be_submitted())

    def test_can_be_submitted_false_when_slot_full(self):
        slot = PickupSlotFactory(food_truck=self.foodtruck, capacity=1)
        order1 = OrderFactory(user=self.user, food_truck=self.foodtruck, pickup_slot=slot)
        order2 = OrderFactory(user=UserFactory(), food_truck=self.foodtruck, pickup_slot=slot)

        order1.add_item(self.item, quantity=1)
        order1.submit()
        order2.add_item(self.item, quantity=1)

        self.assertFalse(order2.can_be_submitted())

    def test_can_be_submitted_false_when_total_price_zero(self):
        free_item = ItemFactory(category=self.category, base_price=Decimal('0.00'))
        order = OrderFactory(user=self.user, food_truck=self.foodtruck, pickup_slot=self.pickup_slot)
        order.add_item(free_item, quantity=1)

        self.assertFalse(order.can_be_submitted())

    def test_submit_changes_status_and_prevents_double_submission(self):
        order = OrderFactory(user=self.user, food_truck=self.foodtruck, pickup_slot=self.pickup_slot)
        order.add_item(self.item, quantity=1)

        order.submit()
        self.assertEqual(order.status, Order.Status.PENDING)

        with self.assertRaises(ValidationError):
            order.submit()

    def test_order_price_snapshot_remains_after_item_price_change(self):
        order = OrderFactory(user=self.user, food_truck=self.foodtruck, pickup_slot=self.pickup_slot)
        order.add_item(self.item, quantity=1)

        self.item.base_price = Decimal('20.00')
        self.item.save()

        order_item = order.items.first()
        self.assertEqual(order_item.unit_price, Decimal('12.00'))
        self.assertEqual(order.total_price, Decimal('12.00'))

    def test_negative_quantity_is_rejected(self):
        order = OrderFactory(user=self.user, food_truck=self.foodtruck, pickup_slot=self.pickup_slot)

        with self.assertRaises(ValidationError):
            order.add_item(self.item, quantity=-1)

    def test_add_combo_adds_order_item_and_updates_total(self):
        order = OrderFactory(user=self.user, food_truck=self.foodtruck, pickup_slot=self.pickup_slot)

        order.add_combo(self.combo, quantity=2)

        self.assertEqual(order.items.count(), 1)
        order_item = order.items.first()
        self.assertEqual(order_item.combo_id, self.combo.id)
        self.assertEqual(order_item.total_price, Decimal('36.00'))
        self.assertEqual(order.total_price, Decimal('36.00'))

    def test_submit_order_with_generated_slot(self):
        schedule = ServiceSchedule.objects.create(
            food_truck=self.foodtruck,
            day_of_week=(timezone.localdate() + timedelta(days=1)).weekday(),
            start_time=time(9, 0),
            end_time=time(10, 0),
            capacity_per_slot=2,
        )
        target_date = timezone.localdate() + timedelta(days=1)
        slot = self.foodtruck.get_available_slots(target_date).first()
        self.assertIsNotNone(slot)

        order = OrderFactory(user=self.user, food_truck=self.foodtruck, pickup_slot=slot)
        order.add_item(self.item, quantity=1)
        order.submit()
        self.assertEqual(order.status, Order.Status.PENDING)

    def test_transition_sequence_follows_operator_lifecycle(self):
        order = OrderFactory(user=self.user, food_truck=self.foodtruck, pickup_slot=self.pickup_slot)
        order.add_item(self.item, quantity=1)
        order.submit()

        order.transition_to(Order.Status.CONFIRMED)
        order.transition_to(Order.Status.PREPARING)
        order.transition_to(Order.Status.READY)
        order.transition_to(Order.Status.COMPLETED)

        self.assertEqual(order.status, Order.Status.COMPLETED)

    def test_cancel_is_only_allowed_from_pending_or_confirmed(self):
        order = OrderFactory(user=self.user, food_truck=self.foodtruck, pickup_slot=self.pickup_slot)
        order.add_item(self.item, quantity=1)
        order.submit()
        order.transition_to(Order.Status.CONFIRMED)
        order.transition_to(Order.Status.PREPARING)

        with self.assertRaises(ValidationError):
            order.transition_to(Order.Status.CANCELLED)

    def test_submit_order_fails_when_slot_full(self):
        schedule = ServiceSchedule.objects.create(
            food_truck=self.foodtruck,
            day_of_week=(timezone.localdate() + timedelta(days=1)).weekday(),
            start_time=time(9, 0),
            end_time=time(9, 20),
            capacity_per_slot=1,
        )
        target_date = timezone.localdate() + timedelta(days=1)
        slot = self.foodtruck.get_available_slots(target_date).first()
        self.assertIsNotNone(slot)

        order1 = OrderFactory(user=self.user, food_truck=self.foodtruck, pickup_slot=slot)
        order1.add_item(self.item, quantity=1)
        order1.submit()

        order2 = OrderFactory(user=UserFactory(), food_truck=self.foodtruck, pickup_slot=slot)
        order2.add_item(self.item, quantity=1)
        with self.assertRaises(ValidationError):
            order2.submit()

    def test_submit_rejects_past_slot(self):
        past_start = timezone.localtime(timezone.now(), PARIS_TZ) - timedelta(hours=1)
        past_end = past_start + timedelta(minutes=10)
        slot = PickupSlotFactory(
            food_truck=self.foodtruck,
            start_time=past_start,
            end_time=past_end,
        )
        order = OrderFactory(user=self.user, food_truck=self.foodtruck, pickup_slot=slot)
        order.add_item(self.item, quantity=1)
        with self.assertRaises(ValidationError):
            order.submit()


class OrderConcurrencyTests(TransactionTestCase):
    def setUp(self):
        self.user = UserFactory()
        self.foodtruck = FoodTruckFactory(owner=self.user)
        self.slot = PickupSlotFactory(food_truck=self.foodtruck, capacity=1)
        self.category = CategoryFactory(menu=MenuFactory(food_truck=self.foodtruck), name='Pizza')
        self.item = ItemFactory(category=self.category, base_price=Decimal('12.00'))

    def test_submit_honors_slot_capacity_under_concurrent_attempts(self):
        order1 = OrderFactory(user=self.user, food_truck=self.foodtruck, pickup_slot=self.slot)
        other_user = UserFactory()
        order2 = OrderFactory(user=other_user, food_truck=self.foodtruck, pickup_slot=self.slot)
        order1.add_item(self.item, quantity=1)
        order2.add_item(self.item, quantity=1)

        results = []
        start_event = threading.Event()

        def attempt_submit(order_id):
            try:
                start_event.wait()
                order = Order.objects.get(pk=order_id)
                order.submit()
                results.append('success')
            except ValidationError:
                results.append('failure')
            except Exception as exc:
                results.append(f'error:{exc}')
            finally:
                connections.close_all()

        threads = [
            threading.Thread(target=attempt_submit, args=(order1.pk,)),
            threading.Thread(target=attempt_submit, args=(order2.pk,))
        ]

        for thread in threads:
            thread.start()

        start_event.set()

        for thread in threads:
            thread.join()

        connections.close_all()

        self.assertEqual(results.count('success'), 1)
        self.assertEqual(results.count('failure'), 1)
        self.assertFalse(any(isinstance(r, str) and r.startswith('error:') for r in results))


class PickupSlotModelTests(TestCase):
    def setUp(self):
        self.foodtruck = FoodTruckFactory()
        self.slot = PickupSlotFactory(food_truck=self.foodtruck, capacity=2)

    def test_is_available_true_when_capacity_not_reached(self):
        self.assertTrue(self.slot.is_available())

    def test_remaining_capacity_reports_available_spots(self):
        self.assertEqual(self.slot.remaining_capacity(), 2)

    def test_slot_becomes_unavailable_at_capacity(self):
        user = UserFactory()
        other = UserFactory()
        order1 = OrderFactory(user=user, food_truck=self.foodtruck, pickup_slot=self.slot)
        order2 = OrderFactory(user=other, food_truck=self.foodtruck, pickup_slot=self.slot)
        item = ItemFactory(category=CategoryFactory(menu=MenuFactory(food_truck=self.foodtruck)))
        order1.add_item(item, quantity=1)
        order2.add_item(item, quantity=1)
        order1.submit()
        order2.submit()

        self.assertFalse(self.slot.is_available())
        self.assertEqual(self.slot.remaining_capacity(), 0)
