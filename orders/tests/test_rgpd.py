from datetime import timedelta
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone

from common.models import AuditLog
from orders.models import Order
from orders.services import DataRetentionService
from orders.tests.factories import CategoryFactory, ItemFactory, MenuFactory, OrderFactory
from payments.tests.factories import PaymentFactory


class OrderRGPDTests(TestCase):
    def _build_paid_order(self, suffix='rgpd', paid_days_ago=120):
        order = OrderFactory(status='draft')
        menu = MenuFactory(food_truck=order.food_truck)
        category = CategoryFactory(menu=menu)
        item = ItemFactory(category=category, name=f'RGPD Item {suffix}', base_price=Decimal('10.00'))
        order.add_item(item, quantity=1)
        order.submit()
        payment = PaymentFactory(order=order, amount=order.total_price, stripe_session_id=f'sess_rgpd_{suffix}')
        payment.mark_as_paid(payment_intent_id=f'pi_rgpd_{suffix}')
        order.refresh_from_db()
        paid_at = timezone.now() - timedelta(days=paid_days_ago)
        Order.objects.filter(pk=order.pk).update(paid_at=paid_at)
        order.refresh_from_db()
        return order

    def test_order_anonymization_removes_personal_data(self):
        order = self._build_paid_order('remove')

        order.anonymize()
        order.refresh_from_db()

        self.assertEqual(order.customer_name, 'ANONYMIZED')
        self.assertIsNone(order.customer_email)
        self.assertIsNone(order.customer_phone)

    def test_order_anonymization_preserves_financial_data(self):
        order = self._build_paid_order('preserve')
        total_amount = order.total_amount
        tax_amount = order.tax_amount
        ticket_id = order.ticket.id
        payment_id = order.payment.id

        order.anonymize()
        order.refresh_from_db()

        self.assertEqual(order.total_amount, total_amount)
        self.assertEqual(order.tax_amount, tax_amount)
        self.assertEqual(order.ticket.id, ticket_id)
        self.assertEqual(order.payment.id, payment_id)

    def test_anonymization_sets_flag(self):
        order = self._build_paid_order('flag')

        order.anonymize()
        order.refresh_from_db()

        self.assertTrue(order.is_anonymized)
        self.assertIsNotNone(order.anonymized_at)
        self.assertTrue(
            AuditLog.objects.filter(action='order_anonymized', model='Order', object_id=str(order.id)).exists()
        )


class DataRetentionServiceTests(TestCase):
    def _build_paid_order(self, suffix='retention', paid_days_ago=120):
        order = OrderFactory(status='draft')
        menu = MenuFactory(food_truck=order.food_truck)
        category = CategoryFactory(menu=menu)
        item = ItemFactory(category=category, name=f'Retention Item {suffix}', base_price=Decimal('11.00'))
        order.add_item(item, quantity=1)
        order.submit()
        payment = PaymentFactory(order=order, amount=order.total_price, stripe_session_id=f'sess_retention_{suffix}')
        payment.mark_as_paid(payment_intent_id=f'pi_retention_{suffix}')
        order.refresh_from_db()
        Order.objects.filter(pk=order.pk).update(paid_at=timezone.now() - timedelta(days=paid_days_ago))
        order.refresh_from_db()
        return order

    def test_only_old_orders_are_anonymized(self):
        old_order = self._build_paid_order('old', paid_days_ago=120)
        recent_order = self._build_paid_order('recent', paid_days_ago=10)

        anonymized_count = DataRetentionService.anonymize_old_orders(days=90)
        old_order.refresh_from_db()
        recent_order.refresh_from_db()

        self.assertEqual(anonymized_count, 1)
        self.assertTrue(old_order.is_anonymized)
        self.assertFalse(recent_order.is_anonymized)

    def test_paid_orders_only_anonymized(self):
        paid_order = self._build_paid_order('paid', paid_days_ago=120)
        draft_order = OrderFactory(status='draft')

        anonymized_count = DataRetentionService.anonymize_old_orders(days=90)
        paid_order.refresh_from_db()
        draft_order.refresh_from_db()

        self.assertEqual(anonymized_count, 1)
        self.assertTrue(paid_order.is_anonymized)
        self.assertFalse(draft_order.is_anonymized)