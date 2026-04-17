from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase

from orders.models import Order
from orders.tests.factories import CategoryFactory, ItemFactory, MenuFactory, OrderFactory
from payments.tests.factories import PaymentFactory


class OrderComplianceTests(TestCase):
    def _build_submitted_order(self):
        order = OrderFactory(status=Order.Status.DRAFT)
        menu = MenuFactory(food_truck=order.food_truck)
        category = CategoryFactory(menu=menu)
        item = ItemFactory(category=category, base_price=Decimal('9.50'))
        order.add_item(item, quantity=2)
        order.submit()
        return order

    def test_paid_order_cannot_be_modified(self):
        order = self._build_submitted_order()
        payment = PaymentFactory(order=order, amount=order.total_price)
        payment.mark_as_paid(payment_intent_id='pi_123')

        order.total_price = Decimal('1.00')
        with self.assertRaises(ValidationError):
            order.save()

    def test_paid_order_cannot_be_deleted(self):
        order = self._build_submitted_order()
        payment = PaymentFactory(order=order, amount=order.total_price)
        payment.mark_as_paid(payment_intent_id='pi_123')

        with self.assertRaises(ValidationError):
            order.delete()

    def test_order_mark_as_paid_is_idempotent(self):
        order = self._build_submitted_order()

        order.mark_as_paid()
        first_paid_at = order.paid_at
        order.mark_as_paid()

        order.refresh_from_db()
        self.assertEqual(order.paid_at, first_paid_at)
        self.assertTrue(order.is_paid())
