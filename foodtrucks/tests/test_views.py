from datetime import time, timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from foodtrucks.tests.factories import FoodTruckFactory
from orders.models import PARIS_TZ
from orders.tests.factories import ServiceScheduleFactory, PickupSlotFactory


class FoodTruckViewTests(TestCase):
    def test_foodtruck_list_view_renders_template(self):
        response = self.client.get(reverse('foodtrucks:foodtruck-list'))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'foodtrucks/list.html')
        self.assertContains(response, 'id="foodtruck-list"')

    def test_foodtruck_detail_view_renders_for_valid_slug(self):
        foodtruck = FoodTruckFactory(name='Barn Burger')
        response = self.client.get(reverse('foodtrucks:foodtruck-detail', kwargs={'slug': foodtruck.slug}))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'foodtrucks/detail.html')
        self.assertEqual(response.context['foodtruck'], foodtruck)
        self.assertContains(response, foodtruck.name)

    def test_foodtruck_detail_view_returns_404_for_invalid_slug(self):
        response = self.client.get(reverse('foodtrucks:foodtruck-detail', kwargs={'slug': 'missing-slug'}))

        self.assertEqual(response.status_code, 404)

    def test_full_page_load_flow_from_list_to_detail(self):
        foodtruck = FoodTruckFactory(name='Barn Burger')

        list_response = self.client.get(reverse('foodtrucks:foodtruck-list'))
        self.assertEqual(list_response.status_code, 200)
        self.assertContains(list_response, 'id="foodtruck-list"')

        detail_response = self.client.get(foodtruck.get_absolute_url())
        self.assertEqual(detail_response.status_code, 200)
        self.assertContains(detail_response, foodtruck.name)

    def test_foodtruck_detail_view_includes_pickup_slot_context(self):
        foodtruck = FoodTruckFactory()
        now = timezone.localtime(timezone.now(), PARIS_TZ)
        schedule = ServiceScheduleFactory(
            food_truck=foodtruck,
            day_of_week=now.weekday(),
            start_time=(now - timedelta(hours=1)).time(),
            end_time=(now + timedelta(hours=2)).time(),
            is_active=True
        )
        slot = PickupSlotFactory(
            food_truck=foodtruck,
            service_schedule=schedule,
            start_time=now + timedelta(minutes=30),
            end_time=now + timedelta(hours=1, minutes=30),
            capacity=5
        )

        response = self.client.get(reverse('foodtrucks:foodtruck-detail', kwargs={'slug': foodtruck.slug}))

        self.assertEqual(response.status_code, 200)
        self.assertIn('available_pickup_slots', response.context)
        self.assertIn('default_pickup_slot_id', response.context)
        self.assertTrue(len(response.context['available_pickup_slots']) > 0)
        self.assertIn(
            response.context['default_pickup_slot_id'],
            [slot_item.id for slot_item in response.context['available_pickup_slots']]
        )

    def test_foodtruck_detail_view_falls_back_to_next_service_slots(self):
        foodtruck = FoodTruckFactory()
        now = timezone.localtime(timezone.now(), PARIS_TZ)
        next_day = (now.weekday() + 1) % 7
        schedule = ServiceScheduleFactory(
            food_truck=foodtruck,
            day_of_week=next_day,
            start_time=time(12, 0),
            end_time=time(14, 0),
            is_active=True,
        )
        next_slot = PickupSlotFactory(
            food_truck=foodtruck,
            service_schedule=schedule,
            start_time=now + timedelta(days=1, hours=1),
            end_time=now + timedelta(days=1, hours=2),
        )

        response = self.client.get(reverse('foodtrucks:foodtruck-detail', kwargs={'slug': foodtruck.slug}))

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['available_pickup_slots'])
        self.assertEqual(
            response.context['available_pickup_slots'][0].service_schedule_id,
            schedule.id,
        )
        self.assertEqual(
            response.context['default_pickup_slot_id'],
            response.context['available_pickup_slots'][0].id,
        )

    def test_foodtruck_detail_view_renders_default_pickup_slot_data_attribute(self):
        foodtruck = FoodTruckFactory()
        now = timezone.localtime(timezone.now(), PARIS_TZ)
        schedule = ServiceScheduleFactory(
            food_truck=foodtruck,
            day_of_week=now.weekday(),
            start_time=(now - timedelta(hours=1)).time(),
            end_time=(now + timedelta(hours=2)).time(),
            is_active=True
        )
        slot = PickupSlotFactory(
            food_truck=foodtruck,
            service_schedule=schedule,
            start_time=now + timedelta(minutes=30),
            end_time=now + timedelta(hours=1, minutes=30),
            capacity=5
        )

        response = self.client.get(reverse('foodtrucks:foodtruck-detail', kwargs={'slug': foodtruck.slug}))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, f'data-default-slot="{response.context["default_pickup_slot_id"]}"')
