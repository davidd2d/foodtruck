from django.test import SimpleTestCase
from django.urls import reverse, resolve
from foodtrucks import views


class FoodTruckURLTests(SimpleTestCase):
    def test_foodtruck_list_url_resolves(self):
        url = reverse('foodtrucks:foodtruck-list')
        self.assertEqual(url, '/foodtrucks/')
        self.assertEqual(resolve(url).func, views.foodtruck_list)

    def test_foodtruck_detail_url_resolves(self):
        url = reverse('foodtrucks:foodtruck-detail', kwargs={'slug': 'barnburger'})
        self.assertEqual(url, '/foodtrucks/barnburger/')
        self.assertEqual(resolve(url).func, views.foodtruck_detail)
