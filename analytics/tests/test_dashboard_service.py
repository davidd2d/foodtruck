from datetime import timedelta
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone

from analytics.services import DashboardService
from foodtrucks.tests.factories import CategoryFactory, FoodTruckFactory, ItemFactory, MenuFactory, UserFactory
from orders.models import OrderItem
from orders.tests.factories import OrderFactory, PickupSlotFactory


class DashboardServiceTests(TestCase):
    def setUp(self):
        self.owner = UserFactory()
        self.foodtruck = FoodTruckFactory(owner=self.owner)
        self.menu = MenuFactory(food_truck=self.foodtruck)
        self.category = CategoryFactory(menu=self.menu)
        self.item_a = ItemFactory(category=self.category, name='Burger')
        self.item_b = ItemFactory(category=self.category, name='Fries')
        self.service = DashboardService(self.foodtruck)

    def _create_order(self, *, paid, amount, status='completed', paid_at=None, slot=None):
        pickup_slot = slot or PickupSlotFactory(food_truck=self.foodtruck)
        order = OrderFactory(
            user=self.owner,
            food_truck=self.foodtruck,
            pickup_slot=pickup_slot,
            status=status,
        )
        order.total_amount = Decimal(amount)
        order.total_price = Decimal(amount)
        order.paid_at = paid_at if paid else None
        order.save(update_fields=['status', 'total_amount', 'total_price', 'paid_at'])
        return order

    def test_kpis_only_use_paid_orders(self):
        now = timezone.now()
        self._create_order(paid=True, amount='20.00', status='completed', paid_at=now)
        self._create_order(paid=True, amount='10.00', status='confirmed', paid_at=now)
        self._create_order(paid=False, amount='999.00', status='pending')

        start_date = timezone.localdate() - timedelta(days=1)
        end_date = timezone.localdate() + timedelta(days=1)

        kpis = self.service.get_kpis(start_date, end_date)

        self.assertEqual(kpis['total_orders'], 2)
        self.assertEqual(kpis['total_revenue'], Decimal('30.00'))
        self.assertEqual(kpis['average_order_value'], Decimal('15.00'))
        self.assertEqual(kpis['completion_rate'], Decimal('50.00'))

    def test_revenue_timeseries_correct(self):
        now = timezone.now()
        self._create_order(paid=True, amount='12.50', status='completed', paid_at=now - timedelta(days=1))
        self._create_order(paid=True, amount='7.50', status='completed', paid_at=now)

        rows = self.service.get_revenue_timeseries(
            start_date=timezone.localdate() - timedelta(days=2),
            end_date=timezone.localdate(),
            interval='day',
        )

        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]['revenue'], Decimal('12.50'))
        self.assertEqual(rows[1]['revenue'], Decimal('7.50'))

    def test_top_items_sorted_by_revenue(self):
        now = timezone.now()
        order_high = self._create_order(paid=False, amount='0.00', status='draft')
        OrderItem.objects.create(
            order=order_high,
            item=self.item_b,
            quantity=2,
            unit_price=Decimal('8.00'),
            tax_rate=Decimal('0.0000'),
            total_price=Decimal('16.00'),
        )
        order_high.paid_at = now
        order_high.status = 'completed'
        order_high.save(update_fields=['paid_at', 'status'])

        order_low = self._create_order(paid=False, amount='0.00', status='draft')
        OrderItem.objects.create(
            order=order_low,
            item=self.item_a,
            quantity=2,
            unit_price=Decimal('5.00'),
            tax_rate=Decimal('0.0000'),
            total_price=Decimal('10.00'),
        )
        order_low.paid_at = now
        order_low.status = 'completed'
        order_low.save(update_fields=['paid_at', 'status'])

        top_items = self.service.get_top_items(limit=10)

        self.assertGreaterEqual(len(top_items), 2)
        self.assertEqual(top_items[0]['product_name'], 'Fries')
        self.assertEqual(top_items[0]['revenue_generated'], Decimal('16.00'))
        self.assertEqual(top_items[1]['product_name'], 'Burger')
        self.assertEqual(top_items[1]['revenue_generated'], Decimal('10.00'))

    def test_slot_performance_calculation(self):
        now = timezone.now()
        slot_a = PickupSlotFactory(
            food_truck=self.foodtruck,
            capacity=4,
            start_time=now + timedelta(hours=1),
            end_time=now + timedelta(hours=2),
        )
        slot_b = PickupSlotFactory(
            food_truck=self.foodtruck,
            capacity=5,
            start_time=now + timedelta(hours=3),
            end_time=now + timedelta(hours=4),
        )

        self._create_order(paid=True, amount='10.00', status='completed', paid_at=now, slot=slot_a)
        self._create_order(paid=True, amount='12.00', status='completed', paid_at=now, slot=slot_a)
        self._create_order(paid=True, amount='8.00', status='completed', paid_at=now, slot=slot_b)
        self._create_order(paid=False, amount='50.00', status='pending', slot=slot_b)

        rows = self.service.get_slot_performance(
            start_date=timezone.localdate() - timedelta(days=1),
            end_date=timezone.localdate() + timedelta(days=1),
        )
        rows_by_slot = {row['slot_id']: row for row in rows}

        self.assertEqual(rows_by_slot[slot_a.id]['orders_count'], 2)
        self.assertEqual(rows_by_slot[slot_a.id]['capacity_usage'], Decimal('50.00'))
        self.assertEqual(rows_by_slot[slot_b.id]['orders_count'], 1)
        self.assertEqual(rows_by_slot[slot_b.id]['capacity_usage'], Decimal('20.00'))
