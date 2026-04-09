from datetime import time, timedelta, datetime

from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APITestCase

from orders.models import ServiceSchedule, PickupSlot
from orders.tests.factories import UserFactory, FoodTruckFactory


class ServiceScheduleAPITests(APITestCase):
    def setUp(self):
        self.user = UserFactory()
        self.foodtruck = FoodTruckFactory(owner=self.user)
        self.client.force_login(self.user)
        self.url = reverse('service-schedule-list')

    def _payload(self):
        return {
            'food_truck': self.foodtruck.id,
            'day_of_week': (timezone.localdate() + timedelta(days=1)).weekday(),
            'start_time': '09:00:00',
            'end_time': '11:00:00',
            'capacity_per_slot': 2,
            'slot_duration_minutes': 15,
            'is_active': True,
        }

    def test_create_schedule(self):
        response = self.client.post(self.url, self._payload(), format='json')
        self.assertEqual(response.status_code, 201)
        self.assertEqual(ServiceSchedule.objects.count(), 1)

    def test_prevent_overlap(self):
        self.client.post(self.url, self._payload(), format='json')
        payload = self._payload()
        payload['start_time'] = '10:00:00'
        payload['end_time'] = '12:00:00'
        response = self.client.post(self.url, payload, format='json')
        self.assertEqual(response.status_code, 400)

    def test_update_schedule(self):
        response = self.client.post(self.url, self._payload(), format='json')
        pk = response.data['id']
        detail_url = reverse('service-schedule-detail', args=[pk])
        patch = {'start_time': '08:00:00'}
        updated = self.client.patch(detail_url, patch, format='json')
        self.assertEqual(updated.status_code, 200)
        self.assertEqual(updated.data['start_time'], '08:00:00')

    def test_delete_schedule(self):
        response = self.client.post(self.url, self._payload(), format='json')
        pk = response.data['id']
        detail_url = reverse('service-schedule-detail', args=[pk])
        delete = self.client.delete(detail_url)
        self.assertEqual(delete.status_code, 204)
        self.assertFalse(ServiceSchedule.objects.filter(pk=pk).exists())


class PickupSlotAPITests(APITestCase):
    def setUp(self):
        self.user = UserFactory()
        self.foodtruck = FoodTruckFactory(owner=self.user)
        self.client.force_login(self.user)
        tomorrow = timezone.localdate() + timedelta(days=1)
        self.date_str = tomorrow.isoformat()
        self.schedule = ServiceSchedule.objects.create(
            food_truck=self.foodtruck,
            day_of_week=tomorrow.weekday(),
            start_time=time(9, 0),
            end_time=time(10, 0),
            capacity_per_slot=2,
            slot_duration_minutes=20,
        )
        self.url = reverse('pickup-slot-generated-list')

    def test_list_slots_generates(self):
        response = self.client.get(self.url, {'foodtruck_slug': self.foodtruck.slug, 'date': self.date_str})
        self.assertEqual(response.status_code, 200)
        results = response.data.get('results', response.data)
        self.assertGreaterEqual(len(results), 1)

    def test_filter_by_date(self):
        response = self.client.get(self.url, {'foodtruck_slug': self.foodtruck.slug, 'date': self.date_str})
        payload = response.data.get('results', response.data)
        payload_date = payload[0]['start_time'][:10]
        self.assertEqual(payload_date, self.date_str)

    def test_invalid_date_param(self):
        response = self.client.get(self.url, {'foodtruck_slug': self.foodtruck.slug, 'date': 'invalid'})
        self.assertEqual(response.status_code, 400)
