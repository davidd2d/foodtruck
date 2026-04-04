from django.test import TestCase
from django.urls import reverse
from foodtrucks.tests.factories import FoodTruckFactory


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
