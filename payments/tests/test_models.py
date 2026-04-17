from django.core.exceptions import ValidationError
from django.test import TestCase

from payments.tests.factories import PaymentFactory


class PaymentModelTests(TestCase):
    def test_is_paid_only_returns_true_for_paid_status(self):
        payment = PaymentFactory(status='pending')
        self.assertFalse(payment.is_paid())

        payment.status = 'paid'
        payment.save(update_fields=['status'])
        self.assertTrue(payment.is_paid())

    def test_mark_as_paid_updates_status_and_intent(self):
        payment = PaymentFactory(status='pending')
        payment.mark_as_paid(payment_intent_id='pi_123')

        payment.refresh_from_db()
        self.assertEqual(payment.status, 'paid')
        self.assertEqual(payment.stripe_payment_intent, 'pi_123')
        self.assertIsNotNone(payment.paid_at)

    def test_mark_as_paid_is_idempotent(self):
        payment = PaymentFactory(status='pending')
        payment.mark_as_paid(payment_intent_id='pi_123')
        first_paid_at = payment.paid_at

        payment.mark_as_paid(payment_intent_id='pi_456')
        payment.refresh_from_db()

        self.assertEqual(payment.status, 'paid')
        self.assertEqual(payment.paid_at, first_paid_at)
        self.assertEqual(payment.stripe_payment_intent, 'pi_123')

    def test_mark_as_failed_from_pending(self):
        payment = PaymentFactory(status='pending')
        payment.mark_as_failed()
        payment.refresh_from_db()

        self.assertEqual(payment.status, 'failed')

    def test_mark_as_failed_rejects_paid_state(self):
        payment = PaymentFactory(status='paid')

        with self.assertRaises(ValidationError):
            payment.mark_as_failed()

    def test_clean_validates_amount(self):
        payment = PaymentFactory(amount='10.00')
        payment.full_clean()  # should not raise

        payment.amount = '-5.00'
        with self.assertRaises(ValidationError):
            payment.full_clean()
