from django.core.exceptions import ValidationError
from django.test import TestCase

from payments.models import Payment
from payments.tests.factories import PaymentFactory


class PaymentModelTests(TestCase):
    def test_is_paid_only_returns_true_for_paid_status(self):
        payment = PaymentFactory(status='pending')
        self.assertFalse(payment.is_paid())

        payment.status = 'paid'
        payment.save(update_fields=['status'])
        self.assertTrue(payment.is_paid())

    def test_can_transition_to_respects_state_machine(self):
        payment = PaymentFactory(status='pending')
        self.assertTrue(payment.can_transition_to('authorized'))
        self.assertFalse(payment.can_transition_to('paid'))

        payment.status = 'authorized'
        self.assertTrue(payment.can_transition_to('paid'))
        self.assertTrue(payment.can_transition_to('failed'))

    def test_transition_to_updates_status_and_provider_id(self):
        payment = PaymentFactory(status='pending')
        payment.transition_to('authorized', provider_payment_id='stripe-session-1')

        payment.refresh_from_db()
        self.assertEqual(payment.status, 'authorized')
        self.assertEqual(payment.provider_payment_id, 'stripe-session-1')

    def test_transition_to_invalid_target_raises(self):
        payment = PaymentFactory(status='pending')

        with self.assertRaises(ValidationError):
            payment.transition_to('paid')

    def test_transition_to_same_state_raises(self):
        payment = PaymentFactory(status='pending')

        with self.assertRaises(ValidationError):
            payment.transition_to('pending')

    def test_clean_validates_amount_and_currency(self):
        payment = PaymentFactory(amount='10.00', currency='EUR')
        payment.full_clean()  # should not raise

        payment.amount = '-5.00'
        with self.assertRaises(ValidationError):
            payment.full_clean()

        payment.amount = '10.00'
        payment.currency = 'EURO'
        with self.assertRaises(ValidationError):
            payment.full_clean()
