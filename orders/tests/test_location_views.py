from decimal import Decimal

from django.test import TestCase
from django.urls import reverse

from orders.models import Location, ServiceSchedule
from orders.tests.factories import FoodTruckFactory, UserFactory


class LocationViewsTests(TestCase):
    def setUp(self):
        self.owner = UserFactory()
        self.other_user = UserFactory()
        self.foodtruck = FoodTruckFactory(owner=self.owner)
        self.schedule = ServiceSchedule.objects.create(
            food_truck=self.foodtruck,
            day_of_week=0,
            start_time='08:00',
            end_time='10:00',
            capacity_per_slot=4,
            slot_duration_minutes=20,
        )

    def client_login(self, user):
        self.client.force_login(user)

    def _location_payload(self):
        return {
            'service_schedule': self.schedule.pk,
            'address_line_1': '123 Owner St',
            'postal_code': '75000',
            'city': 'Paris',
            'country': 'France',
            'latitude': Decimal('48.8566'),
            'longitude': Decimal('2.3522'),
            'is_active': True,
        }

    def test_owner_can_view_locations_list(self):
        Location.objects.create(food_truck=self.foodtruck, **{
            'address_line_1': '123', 'postal_code': '75000', 'city': 'Paris', 'country': 'France',
            'latitude': Decimal('48.8566'), 'longitude': Decimal('2.3522'), 'is_active': True
        })
        self.client_login(self.owner)
        url = reverse('orders:location-list', kwargs={'slug': self.foodtruck.slug})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Base foodtruck location fallback available')

    def test_owner_can_create_location(self):
        self.client_login(self.owner)
        url = reverse('orders:location-create', kwargs={'slug': self.foodtruck.slug})
        response = self.client.post(url, data=self._location_payload())
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Location.objects.filter(food_truck=self.foodtruck).count(), 1)

    def test_owner_can_edit_location(self):
        location = Location.objects.create(food_truck=self.foodtruck, **{
            'address_line_1': '123', 'postal_code': '75000', 'city': 'Paris', 'country': 'France',
            'latitude': Decimal('48.8566'), 'longitude': Decimal('2.3522'), 'is_active': True
        })
        self.client_login(self.owner)
        url = reverse('orders:location-edit', kwargs={'slug': self.foodtruck.slug, 'pk': location.pk})
        response = self.client.post(url, data={**self._location_payload(), 'name': 'Updated Spot'})
        self.assertRedirects(response, reverse('orders:location-list', kwargs={'slug': self.foodtruck.slug}))
        location.refresh_from_db()
        self.assertEqual(location.name, 'Updated Spot')

    def test_owner_can_delete_location(self):
        location = Location.objects.create(food_truck=self.foodtruck, **{
            'address_line_1': '123', 'postal_code': '75000', 'city': 'Paris', 'country': 'France',
            'latitude': Decimal('48.8566'), 'longitude': Decimal('2.3522'), 'is_active': True
        })
        self.client_login(self.owner)
        url = reverse('orders:location-delete', kwargs={'slug': self.foodtruck.slug, 'pk': location.pk})
        response = self.client.post(url)
        self.assertRedirects(response, reverse('orders:location-list', kwargs={'slug': self.foodtruck.slug}))
        location.refresh_from_db()
        self.assertFalse(location.is_active)

    def test_other_user_cannot_access_locations(self):
        self.client_login(self.other_user)
        url = reverse('orders:location-list', kwargs={'slug': self.foodtruck.slug})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)

    def test_navbar_includes_locations_link_for_owner(self):
        self.client_login(self.owner)
        url = reverse('foodtrucks:foodtruck-detail', kwargs={'slug': self.foodtruck.slug})
        response = self.client.get(url)
        self.assertContains(response, 'Locations')
