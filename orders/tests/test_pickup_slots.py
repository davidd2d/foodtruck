from datetime import timedelta

import pytz

from django.test import TestCase
from django.utils import timezone
from django.urls import reverse
from rest_framework.test import APITestCase
from orders.models import PickupSlot
from orders.tests.factories import UserFactory, FoodTruckFactory, PickupSlotFactory, OrderFactory

PARIS_TZ = pytz.timezone('Europe/Paris')


class PickupSlotModelTests(TestCase):
    def setUp(self):
        self.user = UserFactory()
        self.foodtruck = FoodTruckFactory(owner=self.user)
        self.slot = PickupSlotFactory(food_truck=self.foodtruck, capacity=2)

    def test_is_available_future_slot(self):
        self.slot.start_time = timezone.localtime(timezone.now(), PARIS_TZ) + timedelta(hours=2)
        self.slot.end_time = self.slot.start_time + timedelta(hours=1)
        self.slot.save()
        self.assertTrue(self.slot.is_available())

    def test_assign_order_blocks_past_slot(self):
        order = OrderFactory(food_truck=self.foodtruck, user=self.user, status='draft')
        self.slot.start_time = timezone.localtime(timezone.now(), PARIS_TZ) - timedelta(hours=1)
        self.slot.end_time = self.slot.start_time + timedelta(hours=1)
        self.slot.save()
        with self.assertRaises(Exception):
            self.slot.assign_order(order)

    def test_manager_upcoming_for(self):
        future_slot = PickupSlotFactory(food_truck=self.foodtruck, start_time=timezone.localtime(timezone.now(), PARIS_TZ) + timedelta(days=1))
        slots = PickupSlot.objects.upcoming_for(self.foodtruck)
        self.assertIn(future_slot, slots)
        self.assertTrue(all(slot.food_truck == self.foodtruck for slot in slots))


class PickupSlotAPITests(APITestCase):
    def setUp(self):
        self.user = UserFactory()
        self.foodtruck = FoodTruckFactory(owner=self.user)
        self.client.force_login(self.user)
        self.list_url = reverse('pickup-slot-list')

    def make_payload(self, start_delta_hours=2, duration_hours=1):
        start = timezone.localtime(timezone.now(), PARIS_TZ) + timedelta(hours=start_delta_hours)
        end = start + timedelta(hours=duration_hours)
        return {
            'food_truck_id': self.foodtruck.id,
            'start_time': start.isoformat(),
            'end_time': end.isoformat(),
            'capacity': 4,
        }

    def test_create_slot(self):
        response = self.client.post(self.list_url, self.make_payload())
        self.assertEqual(response.status_code, 201)
        self.assertEqual(PickupSlot.objects.filter(food_truck=self.foodtruck).count(), 1)

    def test_create_overlapping_slot_rejected(self):
        payload = self.make_payload()
        self.client.post(self.list_url, payload)
        response = self.client.post(self.list_url, self.make_payload(start_delta_hours=2))
        self.assertEqual(response.status_code, 400)

    def test_owner_cannot_create_for_other_truck(self):
        other_truck = FoodTruckFactory()
        payload = self.make_payload()
        payload['food_truck_id'] = other_truck.id
        response = self.client.post(self.list_url, payload)
        self.assertEqual(response.status_code, 400)

    def test_delete_slot(self):
        payload = self.make_payload()
        response = self.client.post(self.list_url, payload)
        slot_id = response.json()['id']
        detail_url = reverse('pickup-slot-detail', args=[slot_id])
        delete = self.client.delete(detail_url)
        self.assertEqual(delete.status_code, 204)


class SlotManagementViewTests(TestCase):
    def test_owner_sees_page(self):
        user = UserFactory()
        truck = FoodTruckFactory(owner=user)
        client = self.client
        client.force_login(user)
        url = reverse('orders:manage-pickup-slots', kwargs={'slug': truck.slug})
        response = client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Manage Pickup Slots')
