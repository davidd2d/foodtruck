from datetime import timedelta, time
from unittest.mock import patch

import pytest
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APITestCase

from orders.models import ServiceSchedule
from orders.tests.factories import UserFactory, FoodTruckFactory


class TestScheduleAPI(APITestCase):
    def setUp(self):
        self.user = UserFactory()
        self.foodtruck = FoodTruckFactory(owner=self.user)
        self.client.force_login(self.user)
        self.date = timezone.localdate() + timedelta(days=1)
        ServiceSchedule.objects.filter(food_truck=self.foodtruck).delete()
        self.schedule = ServiceSchedule.objects.create(
            food_truck=self.foodtruck,
            day_of_week=self.date.weekday(),
            start_time=time(12, 0),
            end_time=time(14, 0),
            capacity_per_slot=4,
            slot_duration_minutes=10,
        )
        self.url = reverse('service-schedule-list')

    def test_list_triggers_slot_generation(self):
        with patch('orders.api.views.generate_slots_for_date') as mocked:
            response = self.client.get(self.url, {'date': self.date.isoformat()})
            self.assertEqual(response.status_code, 200)
            self.assertTrue(mocked.called)

    def test_slots_created_after_list(self):
        response = self.client.get(self.url, {'date': self.date.isoformat()})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data)
        from orders.models import PickupSlot
        slots = PickupSlot.objects.filter(
            food_truck=self.foodtruck,
            start_time__date=self.date
        )
        self.assertTrue(slots.exists(), 'Slots should exist after listing schedules')
