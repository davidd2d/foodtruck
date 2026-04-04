from decimal import Decimal
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from payments.tests.factories import UserFactory, OrderFactory, PaymentFactory


class PaymentAPITests(APITestCase):
    def setUp(self):
        self.user = UserFactory()
        self.other_user = UserFactory()
        self.order = OrderFactory(customer=self.user, status='submitted', total_price=Decimal('18.75'))
        self.unsubmitted_order = OrderFactory(customer=self.user, status='draft')
        self.other_order = OrderFactory(customer=self.other_user, status='submitted')

    def test_initialize_payment_success(self):
        self.client.force_login(self.user)
        url = reverse('payment-initialize', kwargs={'order_id': self.order.id})
        response = self.client.post(url)

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['order'], self.order.id)
        self.assertEqual(Decimal(response.data['amount']), self.order.total_price)
        self.assertEqual(response.data['status'], 'pending')

    def test_initialize_fails_for_non_submitted_order(self):
        self.client.force_login(self.user)
        url = reverse('payment-initialize', kwargs={'order_id': self.unsubmitted_order.id})
        response = self.client.post(url)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', response.data)

    def test_pay_success_updates_payment_and_order_status(self):
        self.client.force_login(self.user)
        payment = PaymentFactory(order=self.order, status='pending')

        url = reverse('payment-pay', kwargs={'pk': payment.id})
        response = self.client.post(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], 'paid')

        payment.refresh_from_db()
        self.order.refresh_from_db()
        self.assertEqual(payment.status, 'paid')
        self.assertEqual(self.order.status, 'paid')

    def test_pay_fails_if_payment_already_paid(self):
        self.client.force_login(self.user)
        payment = PaymentFactory(order=self.order, status='paid')

        url = reverse('payment-pay', kwargs={'pk': payment.id})
        response = self.client.post(url)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', response.data)

    def test_fail_sets_status_failed(self):
        self.client.force_login(self.user)
        payment = PaymentFactory(order=self.order, status='pending')

        url = reverse('payment-fail', kwargs={'pk': payment.id})
        response = self.client.post(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], 'failed')

        payment.refresh_from_db()
        self.assertEqual(payment.status, 'failed')

    def test_anonymous_user_cannot_initialize_payment(self):
        url = reverse('payment-initialize', kwargs={'order_id': self.order.id})
        response = self.client.post(url)

        self.assertIn(response.status_code, [
            status.HTTP_401_UNAUTHORIZED,
            status.HTTP_403_FORBIDDEN,
        ])

    def test_user_cannot_initialize_other_users_order(self):
        self.client.force_login(self.user)
        url = reverse('payment-initialize', kwargs={'order_id': self.other_order.id})
        response = self.client.post(url)

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_user_cannot_access_other_users_payment(self):
        self.client.force_login(self.user)
        payment = PaymentFactory(order=self.other_order, status='pending')

        url = reverse('payment-pay', kwargs={'pk': payment.id})
        response = self.client.post(url)

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_payment_amount_matches_order_total_on_initialize(self):
        self.client.force_login(self.user)
        url = reverse('payment-initialize', kwargs={'order_id': self.order.id})
        response = self.client.post(url)

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Decimal(response.data['amount']), self.order.total_price)

    def test_double_payment_attempt_is_rejected(self):
        self.client.force_login(self.user)
        payment = PaymentFactory(order=self.order, status='pending')
        self.client.post(reverse('payment-pay', kwargs={'pk': payment.id}))
        response = self.client.post(reverse('payment-pay', kwargs={'pk': payment.id}))

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_payment_after_cancellation_fails(self):
        self.client.force_login(self.user)
        cancelled_order = OrderFactory(customer=self.user, status='cancelled')
        payment = PaymentFactory(order=cancelled_order, status='pending')

        response = self.client.post(reverse('payment-pay', kwargs={'pk': payment.id}))
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
