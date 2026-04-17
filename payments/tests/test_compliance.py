import json
from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase, override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from orders.models import Order
from orders.tests.factories import CategoryFactory, FoodTruckFactory, ItemFactory, MenuFactory, OrderFactory
from payments.models import Payment, StripeEvent
from payments.services.stripe_webhook_service import StripeWebhookService
from payments.tests.factories import PaymentFactory
from payments.tests.factories import UserFactory


class PaymentComplianceTests(TestCase):
    def _build_submitted_order(self):
        order = OrderFactory(status=Order.Status.DRAFT)
        menu = MenuFactory(food_truck=order.food_truck)
        category = CategoryFactory(menu=menu)
        item = ItemFactory(category=category, base_price=Decimal('10.00'))
        order.add_item(item, quantity=1)
        order.submit()
        return order

    def test_payment_mark_as_paid_updates_order(self):
        order = self._build_submitted_order()
        payment = PaymentFactory(order=order, amount=order.total_price)

        payment.mark_as_paid(payment_intent_id='pi_1')

        payment.refresh_from_db()
        order.refresh_from_db()
        self.assertEqual(payment.status, 'paid')
        self.assertEqual(payment.stripe_payment_intent, 'pi_1')
        self.assertIsNotNone(payment.paid_at)
        self.assertIsNotNone(order.paid_at)
        self.assertTrue(order.is_paid())

    def test_payment_cannot_be_processed_twice(self):
        order = self._build_submitted_order()
        payment = PaymentFactory(order=order, amount=order.total_price)

        payment.mark_as_paid(payment_intent_id='pi_1')
        first_paid_at = payment.paid_at

        payment.mark_as_paid(payment_intent_id='pi_2')
        payment.refresh_from_db()

        self.assertEqual(payment.status, 'paid')
        self.assertEqual(payment.paid_at, first_paid_at)
        self.assertEqual(payment.stripe_payment_intent, 'pi_1')


class StripeWebhookComplianceTests(TestCase):
    def _build_payment(self):
        order = OrderFactory(status=Order.Status.DRAFT)
        menu = MenuFactory(food_truck=order.food_truck)
        category = CategoryFactory(menu=menu)
        item = ItemFactory(category=category, base_price=Decimal('12.00'))
        order.add_item(item, quantity=1)
        order.submit()
        payment = Payment.objects.create(
            order=order,
            amount=order.total_price,
            status='pending',
            stripe_session_id='cs_test_123',
        )
        return payment

    @override_settings(STRIPE_WEBHOOK_SECRET='whsec_test')
    def test_webhook_requires_valid_signature(self):
        payload = json.dumps({'id': 'evt_1', 'type': 'checkout.session.completed'}).encode('utf-8')

        with self.assertRaises(Exception):
            StripeWebhookService.construct_event(payload, 't=1,v1=invalid')

    def test_webhook_idempotency(self):
        payment = self._build_payment()
        event = {
            'id': 'evt_once',
            'type': 'checkout.session.completed',
            'data': {
                'object': {
                    'id': payment.stripe_session_id,
                    'payment_intent': 'pi_once',
                    'metadata': {'order_id': str(payment.order_id)},
                }
            },
        }

        first = StripeWebhookService.handle_event(event)
        second = StripeWebhookService.handle_event(event)

        payment.refresh_from_db()
        self.assertTrue(first)
        self.assertFalse(second)
        self.assertEqual(payment.status, 'paid')
        self.assertEqual(StripeEvent.objects.filter(stripe_event_id='evt_once').count(), 1)

    def test_checkout_session_completes_payment(self):
        payment = self._build_payment()
        event = {
            'id': 'evt_checkout_done',
            'type': 'checkout.session.completed',
            'data': {
                'object': {
                    'id': payment.stripe_session_id,
                    'payment_intent': 'pi_checkout_done',
                    'metadata': {'order_id': str(payment.order_id)},
                }
            },
        }

        StripeWebhookService.handle_event(event)

        payment.refresh_from_db()
        payment.order.refresh_from_db()
        self.assertEqual(payment.status, 'paid')
        self.assertEqual(payment.stripe_payment_intent, 'pi_checkout_done')
        self.assertIsNotNone(payment.paid_at)
        self.assertIsNotNone(payment.order.paid_at)

    def test_account_updated_syncs_foodtruck_connect_state(self):
        food_truck = FoodTruckFactory()
        food_truck.stripe_connect_account_id = 'acct_sync'
        food_truck.save(update_fields=['stripe_connect_account_id'])

        event = {
            'id': 'evt_account_updated',
            'type': 'account.updated',
            'data': {
                'object': {
                    'id': 'acct_sync',
                    'details_submitted': True,
                    'charges_enabled': True,
                    'payouts_enabled': True,
                    'metadata': {'food_truck_id': str(food_truck.id)},
                }
            },
        }

        StripeWebhookService.handle_event(event)

        food_truck.refresh_from_db()
        self.assertTrue(food_truck.stripe_onboarding_completed)
        self.assertTrue(food_truck.stripe_details_submitted)
        self.assertTrue(food_truck.stripe_charges_enabled)
        self.assertTrue(food_truck.stripe_payouts_enabled)


class StripeConnectOnboardingAPITests(TestCase):
    def setUp(self):
        self.owner = UserFactory()
        self.owner.is_foodtruck_owner = True
        self.owner.save(update_fields=['is_foodtruck_owner'])
        self.other_user = UserFactory()
        self.food_truck = FoodTruckFactory(owner=self.owner)
        self.client = APIClient()

    @override_settings(STRIPE_SECRET_KEY='sk_test_123')
    @patch('payments.services.stripe_connect_service.stripe.Account.create')
    @patch('payments.services.stripe_connect_service.stripe.AccountLink.create')
    def test_owner_can_create_onboarding_link(self, mock_account_link_create, mock_account_create):
        mock_account_create.return_value = {'id': 'acct_new'}
        mock_account_link_create.return_value = {'url': 'https://connect.stripe.test/onboarding'}
        self.client.force_authenticate(user=self.owner)

        response = self.client.post(reverse('payment-connect-onboarding', kwargs={'slug': self.food_truck.slug}))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['stripe_connect_account_id'], 'acct_new')
        self.assertEqual(response.data['onboarding_url'], 'https://connect.stripe.test/onboarding')

    def test_non_owner_cannot_create_onboarding_link(self):
        self.client.force_authenticate(user=self.other_user)

        response = self.client.post(reverse('payment-connect-onboarding', kwargs={'slug': self.food_truck.slug}))

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
