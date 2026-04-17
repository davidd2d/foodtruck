from decimal import Decimal

from django.test import TestCase
from django.urls import reverse

from orders.tests.factories import CategoryFactory, FoodTruckFactory, ItemFactory, MenuFactory, OrderFactory, UserFactory
from payments.tests.factories import PaymentFactory


def _create_paid_order(user, food_truck, suffix):
    order = OrderFactory(user=user, food_truck=food_truck, status='draft')
    menu = MenuFactory(food_truck=food_truck)
    category = CategoryFactory(menu=menu)
    item = ItemFactory(category=category, name=f'Payment Success Item {suffix}', base_price=Decimal('10.00'))
    order.add_item(item, quantity=1)
    order.submit()

    payment = PaymentFactory(order=order, amount=order.total_price, stripe_session_id=f'sess_success_{suffix}')
    payment.mark_as_paid(payment_intent_id=f'pi_success_{suffix}')
    order.refresh_from_db()
    return order


class PaymentSuccessViewTests(TestCase):
    def setUp(self):
        self.user = UserFactory()
        self.food_truck = FoodTruckFactory(owner=UserFactory())

    def test_success_page_links_to_ticket_page_for_paid_order(self):
        order = _create_paid_order(self.user, self.food_truck, 'ticket-link')
        self.client.force_login(self.user)

        response = self.client.get(reverse(
            'payments:success',
            kwargs={'slug': self.food_truck.slug, 'order_id': order.id},
        ))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, reverse(
            'orders:ticket-detail-page',
            kwargs={'slug': self.food_truck.slug, 'user_id': self.user.id, 'ticket_id': order.ticket.id},
        ))

    def test_checkout_page_requires_matching_foodtruck_slug(self):
        order = _create_paid_order(self.user, self.food_truck, 'slug-check')
        other_truck = FoodTruckFactory(owner=UserFactory())
        self.client.force_login(self.user)

        response = self.client.get(reverse(
            'payments:checkout',
            kwargs={'slug': other_truck.slug, 'order_id': order.id},
        ))

        self.assertEqual(response.status_code, 404)