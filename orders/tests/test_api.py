from datetime import timedelta
from decimal import Decimal
from django.utils import timezone
from rest_framework.test import APITestCase
from rest_framework import status
from rest_framework.reverse import reverse
from django.core.exceptions import ValidationError
from orders.models import Order
from orders.services.cart_service import CartService
from .factories import (
    UserFactory,
    FoodTruckFactory,
    ItemFactory,
    PickupSlotFactory,
    OrderFactory,
    CategoryFactory,
    MenuFactory,
    OptionGroupFactory,
    OptionFactory,
)


class OrderAPITests(APITestCase):
    def setUp(self):
        self.user = UserFactory()
        self.foodtruck = FoodTruckFactory(owner=self.user)
        self.pickup_slot = PickupSlotFactory(food_truck=self.foodtruck)
        self.category = CategoryFactory(menu=MenuFactory(food_truck=self.foodtruck), name='Pizza')
        self.item = ItemFactory(category=self.category, base_price=Decimal('12.00'))
        self.client.force_authenticate(user=self.user)

    def test_create_order(self):
        url = reverse('order-list')
        response = self.client.post(
            url,
            {'food_truck': self.foodtruck.id, 'pickup_slot': self.pickup_slot.id},
            format='json'
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['status'], 'draft')
        self.assertEqual(response.data['total_price'], '0.00')
        self.assertEqual(response.data['customer'], self.user.id)

    def test_add_item_updates_total_price(self):
        order = OrderFactory(user=self.user, food_truck=self.foodtruck, pickup_slot=self.pickup_slot)
        url = reverse('order-add-item', kwargs={'pk': order.id})

        response = self.client.post(
            url,
            {'item_id': self.item.id, 'quantity': 2},
            format='json'
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        order.refresh_from_db()
        self.assertEqual(order.total_price, Decimal('24.00'))

    def test_submit_order_success(self):
        order = OrderFactory(user=self.user, food_truck=self.foodtruck, pickup_slot=self.pickup_slot)
        order.add_item(self.item, quantity=1)

        url = reverse('order-submit', kwargs={'pk': order.id})
        response = self.client.post(url, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], 'order submitted')
        order.refresh_from_db()
        self.assertEqual(order.status, 'submitted')

    def test_submit_empty_order_fails(self):
        order = OrderFactory(user=self.user, food_truck=self.foodtruck, pickup_slot=self.pickup_slot)
        url = reverse('order-submit', kwargs={'pk': order.id})

        response = self.client.post(url, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', response.data)

    def test_submit_slot_full_fails(self):
        slot = PickupSlotFactory(food_truck=self.foodtruck, capacity=1)
        order1 = OrderFactory(user=self.user, food_truck=self.foodtruck, pickup_slot=slot)
        order1.add_item(self.item, quantity=1)
        order1.submit()

        order2 = OrderFactory(user=self.user, food_truck=self.foodtruck, pickup_slot=slot)
        order2.add_item(self.item, quantity=1)

        url = reverse('order-submit', kwargs={'pk': order2.id})
        response = self.client.post(url, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', response.data)

    def test_submit_invalid_state_fails(self):
        order = OrderFactory(user=self.user, food_truck=self.foodtruck, pickup_slot=self.pickup_slot)
        order.add_item(self.item, quantity=1)
        order.submit()

        url = reverse('order-submit', kwargs={'pk': order.id})
        response = self.client.post(url, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', response.data)

    def test_user_cannot_access_another_users_order(self):
        other_user = UserFactory()
        other_order = OrderFactory(user=other_user, food_truck=self.foodtruck, pickup_slot=self.pickup_slot)

        url = reverse('order-detail', kwargs={'pk': other_order.id})
        response = self.client.get(url, format='json')

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_anonymous_cannot_create_order(self):
        self.client.force_authenticate(user=None)
        response = self.client.post(
            reverse('order-list'),
            {'food_truck': self.foodtruck.id, 'pickup_slot': self.pickup_slot.id},
            format='json'
        )

        self.assertIn(response.status_code, [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN])

    def test_invalid_quantity_returns_bad_request(self):
        order = OrderFactory(user=self.user, food_truck=self.foodtruck, pickup_slot=self.pickup_slot)
        url = reverse('order-add-item', kwargs={'pk': order.id})

        response = self.client.post(
            url,
            {'item_id': self.item.id, 'quantity': 0},
            format='json'
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('quantity', response.data)

    def test_add_item_with_options_updates_price(self):
        order = OrderFactory(user=self.user, food_truck=self.foodtruck, pickup_slot=self.pickup_slot)
        option_group = OptionGroupFactory(item=self.item, name='Size')
        option = OptionFactory(group=option_group, name='Large', price_modifier=Decimal('2.00'))
        url = reverse('order-add-item', kwargs={'pk': order.id})

        response = self.client.post(
            url,
            {'item_id': self.item.id, 'quantity': 1, 'selected_options': [option.id]},
            format='json'
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        order.refresh_from_db()
        self.assertEqual(order.total_price, Decimal('14.00'))

    def test_fetch_available_pickup_slots(self):
        url = reverse('foodtruck-pickup-slots', kwargs={'slug': self.foodtruck.slug})
        response = self.client.get(url, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['id'], self.pickup_slot.id)
        self.assertTrue(response.data[0]['is_available'])
        self.assertEqual(response.data[0]['remaining_capacity'], self.pickup_slot.remaining_capacity())

    def test_fetch_available_pickup_slots_falls_back_to_next_available_schedule(self):
        from datetime import timedelta
        from orders.models import ServiceSchedule

        self.pickup_slot.delete()
        tomorrow = timezone.localdate() + timedelta(days=1)
        service_start = timezone.localtime(timezone.now()).replace(hour=10, minute=0, second=0, microsecond=0)
        service_end = service_start.replace(hour=12, minute=0, second=0, microsecond=0)
        next_schedule = ServiceSchedule.objects.create(
            food_truck=self.foodtruck,
            day_of_week=tomorrow.weekday(),
            start_time=service_start.time(),
            end_time=service_end.time(),
            capacity_per_slot=5,
            is_active=True,
        )

        url = reverse('foodtruck-pickup-slots', kwargs={'slug': self.foodtruck.slug})
        response = self.client.get(url, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(len(response.data) > 0)
        self.assertEqual(response.data[0]['service_schedule'], next_schedule.id)
        self.assertTrue(response.data[0]['is_available'])

    def test_set_slot_endpoint_assigns_slot(self):
        order = OrderFactory(user=self.user, food_truck=self.foodtruck, pickup_slot=None)

        url = reverse('order-set-slot')
        response = self.client.post(
            url,
            {'order_id': order.id, 'pickup_slot': self.pickup_slot.id},
            format='json'
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        order.refresh_from_db()
        self.assertEqual(order.pickup_slot_id, self.pickup_slot.id)
        self.assertEqual(response.data['status'], 'pickup slot assigned')

    def test_submit_endpoint_submits_order(self):
        order = OrderFactory(user=self.user, food_truck=self.foodtruck, pickup_slot=self.pickup_slot)
        order.add_item(self.item, quantity=1)

        url = reverse('order-finalize')
        response = self.client.post(url, {'order_id': order.id}, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        order.refresh_from_db()
        self.assertEqual(order.status, 'submitted')
        self.assertEqual(response.data['status'], 'order submitted')

    def test_set_slot_endpoint_rejects_full_slot(self):
        slot = PickupSlotFactory(food_truck=self.foodtruck, capacity=1)
        first = OrderFactory(user=self.user, food_truck=self.foodtruck, pickup_slot=slot)
        first.add_item(self.item, quantity=1)
        first.submit()

        second = OrderFactory(user=self.user, food_truck=self.foodtruck, pickup_slot=None)
        second.add_item(self.item, quantity=1)

        response = self.client.post(
            reverse('order-set-slot'),
            {'order_id': second.id, 'pickup_slot': slot.id},
            format='json'
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', response.data)

    def test_cart_checkout_creates_order(self):
        add_url = reverse('cart-add')
        add_response = self.client.post(
            add_url,
            {
                'foodtruck_slug': self.foodtruck.slug,
                'item_id': self.item.id,
                'quantity': 1,
            },
            format='json'
        )
        self.assertEqual(add_response.status_code, status.HTTP_200_OK)

        url = reverse('cart-checkout')
        response = self.client.post(url, {'pickup_slot': self.pickup_slot.id}, format='json')

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['status'], 'order created')
        self.assertTrue(response.data['order_id'])
        self.assertTrue(Order.objects.filter(id=response.data['order_id'], user=self.user).exists())
