from django.test import TestCase
from foodtrucks.tests.factories import FoodTruckFactory


class FoodTruckModelTests(TestCase):
    def test_slug_is_auto_generated_from_name(self):
        foodtruck = FoodTruckFactory(name='Barn Burger')

        self.assertEqual(foodtruck.slug, 'barn-burger')

    def test_slug_is_unique_for_duplicate_names(self):
        first = FoodTruckFactory(name='Barn Burger')
        second = FoodTruckFactory(name='Barn Burger')

        self.assertNotEqual(first.slug, second.slug)
        self.assertTrue(second.slug.startswith('barn-burger'))

    def test_get_absolute_url_returns_detail_path(self):
        foodtruck = FoodTruckFactory(name='Barn Burger')

        self.assertEqual(foodtruck.get_absolute_url(), f'/foodtrucks/{foodtruck.slug}/')
