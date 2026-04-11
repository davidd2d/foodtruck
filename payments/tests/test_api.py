from decimal import Decimal

from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from accounts.tests.base import JWTAPITestCase
from orders.tests.factories import CategoryFactory, ItemFactory, MenuFactory, OrderFactory
from payments.models import Payment
from payments.services.payment_service import PaymentService
from payments.tests.factories import UserFactory


class PaymentAPITests(JWTAPITestCase):
    def setUp(self):
        self.user = UserFactory()
        self.other_user = UserFactory()
        self.client = APIClient()

    def _prepare_order_with_items(self, user, status='pending'):
        order = OrderFactory(user=user, status='draft')
        menu = MenuFactory(food_truck=order.food_truck)
        category = CategoryFactory(menu=menu)
        item = ItemFactory(category=category, base_price=Decimal('15.00'))
        order.add_item(item, quantity=2)
        order.submit()
        return order

    def test_create_payment_success(self):
        order = self._prepare_order_with_items(self.user)
        self.authenticate_user(self.user)

        response = self.client.post(reverse('payment-create'), {'order_id': order.id})

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Decimal(response.data['amount']), order.total_price)
        self.assertEqual(response.data['status'], 'pending')

    def test_create_payment_requires_pending_order(self):
        order = OrderFactory(user=self.user, status='draft')
        self.authenticate_user(self.user)

        response = self.client.post(reverse('payment-create'), {'order_id': order.id})

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_payment_requires_order_ownership(self):
        order = self._prepare_order_with_items(self.other_user)
        self.authenticate_user(self.user)

        response = self.client.post(reverse('payment-create'), {'order_id': order.id})
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_authorize_payment_success(self):
        order = self._prepare_order_with_items(self.user)
        self.authenticate_user(self.user)
        payment = PaymentService.create_payment(order)

        response = self.client.post(reverse('payment-authorize'), {'payment_id': payment.id})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], 'authorized')

    def test_authorize_payment_missing_payment(self):
        self.authenticate_user(self.user)
        response = self.client.post(reverse('payment-authorize'), {'payment_id': 999})

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_capture_payment_keeps_order_in_operator_flow(self):
        order = self._prepare_order_with_items(self.user)
        self.authenticate_user(self.user)
        payment = PaymentService.create_payment(order)
        PaymentService.authorize_payment(payment)

        response = self.client.post(reverse('payment-capture'), {'payment_id': payment.id})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], 'paid')
        order.refresh_from_db()
        self.assertEqual(order.status, 'pending')

    def test_capture_requires_authorized_payment(self):
        order = self._prepare_order_with_items(self.user)
        self.authenticate_user(self.user)
        payment = PaymentService.create_payment(order)

        response = self.client.post(reverse('payment-capture'), {'payment_id': payment.id})

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_user_cannot_capture_other_users_payment(self):
        order = self._prepare_order_with_items(self.other_user)
        payment = PaymentService.create_payment(order)
        PaymentService.authorize_payment(payment)

        self.authenticate_user(self.user)
        response = self.client.post(reverse('payment-capture'), {'payment_id': payment.id})

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_full_payment_flow_integration(self):
        order = self._prepare_order_with_items(self.user)
        self.authenticate_user(self.user)

        created = self.client.post(reverse('payment-create'), {'order_id': order.id})
        self.assertEqual(created.status_code, status.HTTP_201_CREATED)

        payment_id = created.data['id']

        authorized = self.client.post(reverse('payment-authorize'), {'payment_id': payment_id})
        self.assertEqual(authorized.status_code, status.HTTP_200_OK)

        captured = self.client.post(reverse('payment-capture'), {'payment_id': payment_id})
        self.assertEqual(captured.status_code, status.HTTP_200_OK)

        order.refresh_from_db()
        self.assertEqual(order.status, 'pending')
        payment = Payment.objects.get(id=payment_id)
        self.assertEqual(payment.status, 'paid')
