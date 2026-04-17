from decimal import Decimal

from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from orders.models import Order
from orders.tests.factories import CategoryFactory, FoodTruckFactory, ItemFactory, MenuFactory, OrderFactory, UserFactory
from payments.tests.factories import PaymentFactory


def _create_paid_order(user, food_truck, suffix):
    order = OrderFactory(user=user, food_truck=food_truck, status=Order.Status.DRAFT)
    menu = MenuFactory(food_truck=food_truck)
    category = CategoryFactory(menu=menu)
    item = ItemFactory(category=category, name=f'Ticket Item {suffix}', base_price=Decimal('10.00'))
    order.add_item(item, quantity=1)
    order.submit()

    payment = PaymentFactory(order=order, amount=order.total_price, stripe_session_id=f'sess_access_{suffix}')
    payment.mark_as_paid(payment_intent_id=f'pi_access_{suffix}')
    order.refresh_from_db()
    return order


class TicketPageTests(TestCase):
    def setUp(self):
        self.user = UserFactory()
        self.other_user = UserFactory()
        self.food_truck = FoodTruckFactory(owner=self.user)

    def test_ticket_list_page_requires_authentication(self):
        response = self.client.get(reverse(
            'orders:ticket-list-page',
            kwargs={'slug': self.food_truck.slug, 'user_id': self.user.id},
        ))
        self.assertEqual(response.status_code, 302)

    def test_ticket_list_page_shows_only_user_tickets(self):
        own_order = _create_paid_order(self.user, self.food_truck, 'own')
        other_truck = FoodTruckFactory(owner=self.other_user)
        other_order = _create_paid_order(self.other_user, other_truck, 'other')

        self.client.force_login(self.user)
        response = self.client.get(reverse(
            'orders:ticket-list-page',
            kwargs={'slug': self.food_truck.slug, 'user_id': self.user.id},
        ))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, own_order.ticket.number)
        self.assertNotContains(response, other_order.ticket.number)
        self.assertContains(response, 'Ticket Item own')

    def test_ticket_list_page_can_display_selected_ticket_inline(self):
        first_order = _create_paid_order(self.user, self.food_truck, 'first')
        second_order = _create_paid_order(self.user, self.food_truck, 'second')

        self.client.force_login(self.user)
        response = self.client.get(
            reverse('orders:ticket-list-page', kwargs={'slug': self.food_truck.slug, 'user_id': self.user.id}),
            {'ticket': second_order.ticket.id},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Ticket Item second')
        self.assertNotContains(response, 'Ticket Item first')

    def test_ticket_list_page_rejects_other_user_identifier(self):
        self.client.force_login(self.user)

        response = self.client.get(reverse(
            'orders:ticket-list-page',
            kwargs={'slug': self.food_truck.slug, 'user_id': self.other_user.id},
        ))

        self.assertEqual(response.status_code, 404)

    def test_ticket_detail_page_displays_ticket_payload(self):
        order = _create_paid_order(self.user, self.food_truck, 'detail')

        self.client.force_login(self.user)
        response = self.client.get(reverse(
            'orders:ticket-detail-page',
            kwargs={'slug': self.food_truck.slug, 'user_id': self.user.id, 'ticket_id': order.ticket.id},
        ))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, order.ticket.number)
        self.assertContains(response, 'Ticket Item detail')

    def test_ticket_detail_page_rejects_other_user(self):
        order = _create_paid_order(self.user, self.food_truck, 'forbidden')

        self.client.force_login(self.other_user)
        response = self.client.get(reverse(
            'orders:ticket-detail-page',
            kwargs={'slug': self.food_truck.slug, 'user_id': self.user.id, 'ticket_id': order.ticket.id},
        ))

        self.assertEqual(response.status_code, 404)

    def test_owner_ticket_list_page_shows_customer_tickets(self):
        own_order = _create_paid_order(self.other_user, self.food_truck, 'owner-view')

        self.client.force_login(self.user)
        response = self.client.get(reverse('orders:owner-ticket-list', kwargs={'slug': self.food_truck.slug}))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, own_order.ticket.number)
        self.assertContains(response, self.other_user.email)

    def test_non_owner_cannot_access_owner_ticket_list_page(self):
        self.client.force_login(self.other_user)

        response = self.client.get(reverse('orders:owner-ticket-list', kwargs={'slug': self.food_truck.slug}))

        self.assertEqual(response.status_code, 404)


class TicketAPITests(APITestCase):
    def setUp(self):
        self.customer = UserFactory()
        self.owner = UserFactory()
        self.outsider = UserFactory()
        self.truck = FoodTruckFactory(owner=self.owner)

    def test_customer_can_list_own_tickets(self):
        own_order = _create_paid_order(self.customer, self.truck, 'cust')

        self.client.force_authenticate(user=self.customer)
        response = self.client.get(reverse('ticket-list'))
        payload = response.data.get('results', response.data)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(payload), 1)
        self.assertEqual(payload[0]['number'], own_order.ticket.number)

    def test_owner_can_list_tickets_for_owned_foodtruck(self):
        order = _create_paid_order(self.customer, self.truck, 'owner')

        self.client.force_authenticate(user=self.owner)
        response = self.client.get(reverse('ticket-list'))
        payload = response.data.get('results', response.data)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(payload), 1)
        self.assertEqual(payload[0]['number'], order.ticket.number)

    def test_outsider_cannot_access_ticket(self):
        order = _create_paid_order(self.customer, self.truck, 'outsider')

        self.client.force_authenticate(user=self.outsider)
        detail_url = reverse('ticket-detail', kwargs={'pk': order.ticket.pk})
        response = self.client.get(detail_url)

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
