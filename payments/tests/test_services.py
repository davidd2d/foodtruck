from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase

from orders.tests.factories import CategoryFactory, ItemFactory, MenuFactory, OrderFactory
from payments.models import Payment
from payments.services.payment_service import PaymentService


class PaymentServiceTests(TestCase):
    """Ensure payment creation and lifecycle helpers behave declaratively."""

    def _prepare_pending_order(self):
        """Create an order with items and submit it."""
        order = OrderFactory(status='draft')
        menu = MenuFactory(food_truck=order.food_truck)
        category = CategoryFactory(menu=menu)
        item = ItemFactory(category=category, base_price=Decimal('11.00'))
        order.add_item(item, quantity=1)
        order.submit()
        return order

    def test_create_payment_creates_pending_payment(self):
        order = self._prepare_pending_order()
        payment = PaymentService.create_payment(order)

        self.assertEqual(payment.status, 'pending')
        self.assertEqual(payment.amount, order.calculate_total())
        self.assertEqual(payment.order_id, order.id)

    def test_create_payment_rejects_empty_order(self):
        order = OrderFactory(status='pending')

        with self.assertRaises(ValidationError):
            PaymentService.create_payment(order)

    def test_create_payment_prevents_duplicate(self):
        order = self._prepare_pending_order()
        PaymentService.create_payment(order)

        with self.assertRaises(ValidationError):
            PaymentService.create_payment(order)

    def test_authorize_payment_transitions_to_authorized(self):
        order = self._prepare_pending_order()
        payment = PaymentService.create_payment(order)

        PaymentService.authorize_payment(payment)

        self.assertEqual(payment.status, 'authorized')

    def test_capture_payment_keeps_operator_status_unchanged(self):
        order = self._prepare_pending_order()
        payment = PaymentService.create_payment(order)
        PaymentService.authorize_payment(payment)

        PaymentService.capture_payment(payment)

        payment.refresh_from_db()
        order.refresh_from_db()
        self.assertEqual(payment.status, 'paid')
        self.assertEqual(order.status, 'pending')
        self.assertTrue(order.is_paid())

    def test_capture_payment_rejects_already_paid_order(self):
        order = self._prepare_pending_order()
        payment = PaymentService.create_payment(order)
        PaymentService.authorize_payment(payment)
        PaymentService.capture_payment(payment)

        with self.assertRaises(ValidationError):
            PaymentService.capture_payment(payment)

    def test_fail_payment_transitions_to_failed(self):
        order = self._prepare_pending_order()
        payment = PaymentService.create_payment(order)
        PaymentService.authorize_payment(payment)
        PaymentService.fail_payment(payment)

        self.assertEqual(payment.status, 'failed')
