from decimal import Decimal
from django.core.exceptions import ValidationError
from django.test import TestCase
from orders.models import Order
from payments.models import Payment
from payments.tests.factories import UserFactory, OrderFactory, PaymentFactory


class PaymentModelTests(TestCase):
    def test_initialize_sets_status_pending_and_copies_order_amount(self):
        order = OrderFactory(status='submitted', total_price=Decimal('32.50'))
        payment = PaymentFactory(order=order, amount=Decimal('1.00'), status='pending')

        payment.amount = Decimal('1.00')
        payment.status = 'failed'
        payment.initialize()

        payment.refresh_from_db()
        self.assertEqual(payment.status, 'pending')
        self.assertEqual(payment.amount, order.total_price)

    def test_initialize_fails_if_order_not_submitted(self):
        order = OrderFactory(status='draft')
        payment = PaymentFactory(order=order, amount=Decimal('12.00'), status='pending')

        with self.assertRaises(ValidationError):
            payment.initialize()

    def test_mark_as_paid_updates_payment_and_order_status(self):
        order = OrderFactory(status='submitted')
        payment = PaymentFactory(order=order, status='pending')

        payment.mark_as_paid()

        payment.refresh_from_db()
        order.refresh_from_db()
        self.assertEqual(payment.status, 'paid')
        self.assertEqual(order.status, 'paid')
        self.assertTrue(order.is_paid())

    def test_mark_as_paid_cannot_be_called_twice(self):
        order = OrderFactory(status='submitted')
        payment = PaymentFactory(order=order, status='pending')
        payment.mark_as_paid()

        with self.assertRaises(ValidationError):
            payment.mark_as_paid()

    def test_mark_as_failed_sets_failed_status(self):
        order = OrderFactory(status='submitted')
        payment = PaymentFactory(order=order, status='pending')

        payment.mark_as_failed()
        self.assertEqual(payment.status, 'failed')

    def test_refund_only_allowed_for_paid_payment(self):
        order = OrderFactory(status='submitted')
        payment = PaymentFactory(order=order, status='paid')

        payment.refund()
        self.assertEqual(payment.status, 'refunded')

    def test_refund_before_payment_raises_validation_error(self):
        order = OrderFactory(status='submitted')
        payment = PaymentFactory(order=order, status='pending')

        with self.assertRaises(ValidationError):
            payment.refund()

    def test_order_is_paid_returns_true_when_payment_paid(self):
        order = OrderFactory(status='submitted')
        PaymentFactory(order=order, status='paid')

        self.assertTrue(order.is_paid())

    def test_cannot_initialize_second_payment_for_same_order(self):
        order = OrderFactory(status='submitted')
        existing_payment = PaymentFactory(order=order, status='pending')
        second_payment = Payment(order=order, amount=order.total_price, status='pending')

        with self.assertRaises(ValidationError):
            second_payment.initialize()

    def test_cannot_pay_order_not_in_submitted_state(self):
        order = OrderFactory(status='cancelled')
        payment = PaymentFactory(order=order, status='pending')

        with self.assertRaises(ValidationError):
            payment.mark_as_paid()
