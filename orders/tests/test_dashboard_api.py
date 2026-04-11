from decimal import Decimal

from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from orders.models import Order
from orders.tests.factories import CategoryFactory, FoodTruckFactory, ItemFactory, MenuFactory, OptionFactory, OptionGroupFactory, OrderFactory, PickupSlotFactory, UserFactory


class OrderDashboardAPITests(APITestCase):
    def setUp(self):
        self.owner = UserFactory()
        self.other_owner = UserFactory()
        self.foodtruck = FoodTruckFactory(owner=self.owner)
        self.other_foodtruck = FoodTruckFactory(owner=self.other_owner, name='Other truck')
        self.slot = PickupSlotFactory(food_truck=self.foodtruck)
        self.category = CategoryFactory(menu=MenuFactory(food_truck=self.foodtruck))
        self.item = ItemFactory(category=self.category, base_price=Decimal('12.00'))
        self.client.force_authenticate(user=self.owner)

    def _create_pending_order(self):
        order = OrderFactory(user=self.owner, food_truck=self.foodtruck, pickup_slot=self.slot, status=Order.Status.DRAFT)
        order.add_item(self.item, quantity=1)
        order.submit()
        return order

    def test_dashboard_api_lists_owner_orders(self):
        order = self._create_pending_order()

        response = self.client.get(reverse('orders:dashboard-api'))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['id'], order.id)
        self.assertEqual(response.data[0]['status'], Order.Status.PENDING)
        self.assertEqual(response.data[0]['items'][0]['item_name'], self.item.name)

    def test_dashboard_api_returns_selected_options_for_each_line(self):
        option_group = OptionGroupFactory(item=self.item, min_choices=0, max_choices=2)
        spicy = OptionFactory(group=option_group, name='Spicy mayo')
        onions = OptionFactory(group=option_group, name='Pickled onions')
        order = OrderFactory(user=self.owner, food_truck=self.foodtruck, pickup_slot=self.slot, status=Order.Status.DRAFT)
        order.add_item(self.item, quantity=2, selected_options=[spicy.id, onions.id])
        order.submit()

        response = self.client.get(reverse('orders:dashboard-api'))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        line = response.data[0]['items'][0]
        self.assertEqual(line['quantity'], 2)
        self.assertEqual(
            [entry['name'] for entry in line['selected_options']],
            ['Spicy mayo', 'Pickled onions'],
        )

    def test_dashboard_api_filters_by_status(self):
        self._create_pending_order()
        confirmed = self._create_pending_order()
        confirmed.transition_to(Order.Status.CONFIRMED)
        confirmed.save(update_fields=['status'])

        response = self.client.get(reverse('orders:dashboard-api'), {'status': Order.Status.CONFIRMED})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual([entry['id'] for entry in response.data], [confirmed.id])

    def test_dashboard_api_excludes_other_owner_orders(self):
        foreign_slot = PickupSlotFactory(food_truck=self.other_foodtruck)
        foreign_category = CategoryFactory(menu=MenuFactory(food_truck=self.other_foodtruck))
        foreign_item = ItemFactory(category=foreign_category, base_price=Decimal('10.00'))
        foreign_order = OrderFactory(user=self.other_owner, food_truck=self.other_foodtruck, pickup_slot=foreign_slot, status=Order.Status.DRAFT)
        foreign_order.add_item(foreign_item, quantity=1)
        foreign_order.submit()

        response = self.client.get(reverse('orders:dashboard-api'))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, [])

    def test_dashboard_status_update_accepts_valid_transition(self):
        order = self._create_pending_order()

        response = self.client.post(
            reverse('orders:dashboard-status-api', kwargs={'order_id': order.id}),
            {'status': Order.Status.CONFIRMED},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.CONFIRMED)

    def test_dashboard_status_update_rejects_invalid_transition(self):
        order = self._create_pending_order()

        response = self.client.post(
            reverse('orders:dashboard-status-api', kwargs={'order_id': order.id}),
            {'status': Order.Status.COMPLETED},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.PENDING)