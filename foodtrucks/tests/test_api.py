from rest_framework.test import APITestCase
from rest_framework import status
from rest_framework.reverse import reverse
from foodtrucks.tests.factories import (
    UserFactory,
    PreferenceFactory,
    FoodTruckFactory,
    PickupSlotFactory,
)


class FoodTruckAPITests(APITestCase):
    def setUp(self):
        self.user = UserFactory()
        self.pref_vegan = PreferenceFactory(name='Vegan')
        self.pref_gluten_free = PreferenceFactory(name='Gluten Free')

        self.truck_a = FoodTruckFactory(name='Pizza Express', latitude=40.0, longitude=-73.0)
        self.truck_a.supported_preferences.add(self.pref_vegan)

        self.truck_b = FoodTruckFactory(name='Burger House', latitude=40.001, longitude=-73.001)
        self.truck_b.supported_preferences.add(self.pref_gluten_free)

        self.truck_c = FoodTruckFactory(name='Taco Stand', latitude=41.0, longitude=-74.0, is_active=False)

    def test_list_all_active_foodtrucks(self):
        response = self.client.get(reverse('foodtruck-list'))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        ids = {item['id'] for item in self.get_list_results(response)}
        self.assertIn(self.truck_a.id, ids)
        self.assertIn(self.truck_b.id, ids)
        self.assertNotIn(self.truck_c.id, ids)

    def test_exclude_inactive_foodtrucks(self):
        response = self.client.get(reverse('foodtruck-list'))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = self.get_list_results(response)
        self.assertEqual(len(results), 2)
        self.assertNotIn(self.truck_c.id, [item['id'] for item in results])

    def get_list_results(self, response):
        if isinstance(response.data, dict) and 'results' in response.data:
            return response.data['results']
        return response.data

    def test_filter_by_preference(self):
        response = self.client.get(reverse('foodtruck-list') + f'?supported_preferences={self.pref_vegan.id}')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = self.get_list_results(response)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]['id'], self.truck_a.id)

    def test_search_by_name(self):
        response = self.client.get(reverse('foodtruck-list') + '?search=Burger')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = self.get_list_results(response)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]['id'], self.truck_b.id)

    def test_distance_filter_returns_nearby_foodtrucks(self):
        response = self.client.get(reverse('foodtruck-list') + '?lat=40.0&lng=-73.0&radius=5')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = self.get_list_results(response)
        ids = {item['id'] for item in results}
        self.assertIn(self.truck_a.id, ids)
        self.assertIn(self.truck_b.id, ids)
        self.assertNotIn(self.truck_c.id, ids)

    def test_distance_filter_ignores_invalid_coordinates(self):
        response = self.client.get(reverse('foodtruck-list') + '?lat=bad&lng=bad&radius=5')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = self.get_list_results(response)
        self.assertEqual(len(results), 2)

    def test_retrieve_foodtruck_detail_includes_preferences_and_branding(self):
        url = reverse('foodtruck-detail', kwargs={'pk': self.truck_a.id})
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['id'], self.truck_a.id)
        self.assertEqual(response.data['name'], self.truck_a.name)
        self.assertIn('supported_preferences', response.data)
        self.assertIn('primary_color', response.data)
        self.assertIn('secondary_color', response.data)
