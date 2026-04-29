from datetime import timedelta
from decimal import Decimal

import pytz

from django.test import TestCase
from django.utils import timezone

_LOCAL_TZ = pytz.timezone('Europe/Paris')

from analytics.services import DashboardService
from foodtrucks.tests.factories import FoodTruckFactory, UserFactory
from foodtrucks.tests.factories import CategoryFactory, ItemFactory, MenuFactory
from orders.models import OrderItem
from orders.tests.factories import OrderFactory, PickupSlotFactory


class SlotAnalyticsServiceTests(TestCase):
    def setUp(self):
        self.owner = UserFactory()
        self.foodtruck = FoodTruckFactory(owner=self.owner)
        self.service = DashboardService(self.foodtruck)
        self.menu = MenuFactory(food_truck=self.foodtruck)
        self.category_a = CategoryFactory(menu=self.menu, name='Pasta')
        self.category_b = CategoryFactory(menu=self.menu, name='Dessert')
        self.item_a = ItemFactory(category=self.category_a, name='Pasta Box')
        self.item_b = ItemFactory(category=self.category_b, name='Tiramisu')

    def _create_paid_order(self, slot, amount='10.00', paid_at=None, status='completed'):
        order = OrderFactory(
            user=self.owner,
            food_truck=self.foodtruck,
            pickup_slot=slot,
            status=status,
        )
        order.total_amount = Decimal(amount)
        order.total_price = Decimal(amount)
        order.paid_at = paid_at or timezone.now()
        order.save(update_fields=['status', 'total_amount', 'total_price', 'paid_at'])
        return order

    def test_slot_utilization_calculation(self):
        now = timezone.now()
        slot = PickupSlotFactory(
            food_truck=self.foodtruck,
            capacity=4,
            start_time=now + timedelta(hours=2),
            end_time=now + timedelta(hours=3),
        )
        self._create_paid_order(slot, amount='12.00', paid_at=now)
        self._create_paid_order(slot, amount='8.00', paid_at=now)

        rows = self.service.get_slot_utilization(
            start_date=timezone.localdate() - timedelta(days=1),
            end_date=timezone.localdate() + timedelta(days=1),
        )
        row = next(entry for entry in rows if entry['slot_id'] == slot.id)

        self.assertEqual(row['total_orders'], 2)
        self.assertEqual(row['capacity'], 4)
        self.assertEqual(row['utilization_rate'], Decimal('0.5000'))

    def test_hourly_grouping(self):
        now = timezone.now().replace(minute=0, second=0, microsecond=0)
        utc_12 = now.replace(hour=12)
        utc_13 = now.replace(hour=13)
        local_12 = utc_12.astimezone(_LOCAL_TZ).hour
        local_13 = utc_13.astimezone(_LOCAL_TZ).hour
        slot_12 = PickupSlotFactory(
            food_truck=self.foodtruck,
            capacity=5,
            start_time=utc_12,
            end_time=utc_12 + timedelta(hours=1),
        )
        slot_13 = PickupSlotFactory(
            food_truck=self.foodtruck,
            capacity=5,
            start_time=utc_13,
            end_time=utc_13 + timedelta(hours=1),
        )
        self._create_paid_order(slot_12, amount='10.00', paid_at=timezone.now())
        self._create_paid_order(slot_12, amount='20.00', paid_at=timezone.now())
        self._create_paid_order(slot_13, amount='15.00', paid_at=timezone.now())

        rows = self.service.get_hourly_performance(
            start_date=timezone.localdate() - timedelta(days=1),
            end_date=timezone.localdate() + timedelta(days=1),
        )
        by_hour = {entry['hour']: entry for entry in rows}

        self.assertEqual(by_hour[local_12]['orders'], 2)
        self.assertEqual(by_hour[local_12]['revenue'], Decimal('30.00'))
        self.assertEqual(by_hour[local_13]['orders'], 1)

    def test_weekday_grouping(self):
        monday = timezone.now().replace(hour=12, minute=0, second=0, microsecond=0)
        while monday.weekday() != 0:
            monday += timedelta(days=1)

        tuesday = monday + timedelta(days=1)

        slot_mon = PickupSlotFactory(
            food_truck=self.foodtruck,
            capacity=5,
            start_time=monday,
            end_time=monday + timedelta(hours=1),
        )
        slot_tue = PickupSlotFactory(
            food_truck=self.foodtruck,
            capacity=5,
            start_time=tuesday,
            end_time=tuesday + timedelta(hours=1),
        )

        self._create_paid_order(slot_mon, amount='11.00', paid_at=timezone.now())
        self._create_paid_order(slot_tue, amount='22.00', paid_at=timezone.now())

        rows = self.service.get_weekday_performance()
        by_weekday = {entry['weekday']: entry for entry in rows}

        self.assertEqual(by_weekday[0]['orders'], 1)
        self.assertEqual(by_weekday[0]['revenue'], Decimal('11.00'))
        self.assertEqual(by_weekday[1]['orders'], 1)

    def test_heatmap_data_structure(self):
        now = timezone.now().replace(hour=12, minute=0, second=0, microsecond=0)
        slot = PickupSlotFactory(
            food_truck=self.foodtruck,
            capacity=5,
            start_time=now,
            end_time=now + timedelta(hours=1),
        )
        self._create_paid_order(slot, amount='10.00', paid_at=timezone.now())

        rows = self.service.get_slot_heatmap(
            start_date=timezone.localdate() - timedelta(days=1),
            end_date=timezone.localdate() + timedelta(days=1),
        )

        self.assertTrue(rows)
        first = rows[0]
        self.assertIn('weekday', first)
        self.assertIn('hour', first)
        self.assertIn('orders', first)

    def test_recommendation_logic(self):
        now = timezone.now().replace(minute=0, second=0, microsecond=0)
        slot_saturated = PickupSlotFactory(
            food_truck=self.foodtruck,
            capacity=2,
            start_time=now.replace(hour=12),
            end_time=now.replace(hour=13),
        )
        slot_low = PickupSlotFactory(
            food_truck=self.foodtruck,
            capacity=10,
            start_time=now.replace(hour=10),
            end_time=now.replace(hour=11),
        )

        self._create_paid_order(slot_saturated, amount='12.00', paid_at=timezone.now())
        self._create_paid_order(slot_saturated, amount='15.00', paid_at=timezone.now())
        self._create_paid_order(slot_low, amount='5.00', paid_at=timezone.now())

        recommendations = self.service.get_slot_recommendations()

        self.assertTrue(any(row['slot_id'] == slot_saturated.id for row in recommendations['increase_capacity_slots']))
        self.assertTrue(any(row['slot_id'] == slot_low.id for row in recommendations['reduce_capacity_slots']))
        self.assertTrue(any(row['hour'] in [11, 13] for row in recommendations['suggested_new_slots']))

    def test_category_performance_grouping(self):
        now = timezone.now()
        slot = PickupSlotFactory(
            food_truck=self.foodtruck,
            capacity=6,
            start_time=now + timedelta(hours=1),
            end_time=now + timedelta(hours=2),
        )

        order = OrderFactory(
            user=self.owner,
            food_truck=self.foodtruck,
            pickup_slot=slot,
            status='draft',
        )
        OrderItem.objects.create(
            order=order,
            item=self.item_a,
            quantity=2,
            unit_price=Decimal('9.00'),
            tax_rate=Decimal('0.0000'),
            total_price=Decimal('18.00'),
        )
        OrderItem.objects.create(
            order=order,
            item=self.item_b,
            quantity=1,
            unit_price=Decimal('6.00'),
            tax_rate=Decimal('0.0000'),
            total_price=Decimal('6.00'),
        )

        order.total_amount = Decimal('24.00')
        order.total_price = Decimal('24.00')
        order.status = 'completed'
        order.paid_at = now
        order.save(update_fields=['total_amount', 'total_price', 'status', 'paid_at'])

        rows = self.service.get_category_performance(
            start_date=timezone.localdate() - timedelta(days=1),
            end_date=timezone.localdate() + timedelta(days=1),
            limit=8,
        )

        by_category = {row['category_name']: row for row in rows}
        self.assertEqual(by_category['Pasta']['quantity_sold'], 2)
        self.assertEqual(by_category['Pasta']['revenue_generated'], Decimal('18.00'))
        self.assertEqual(by_category['Dessert']['quantity_sold'], 1)
