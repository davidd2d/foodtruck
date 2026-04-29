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

    def test_foodtruck_dashboard_url_resolves(self):
        url = reverse('foodtrucks:foodtruck-dashboard', kwargs={'slug': 'barnburger'})
        self.assertEqual(url, '/foodtrucks/barnburger/dashboard/')
        self.assertEqual(resolve(url).func.view_class, views.FoodTruckDashboardView)

    def test_foodtruck_dashboard_kpis_url_resolves(self):
        url = reverse('foodtrucks:foodtruck-dashboard-kpis', kwargs={'slug': 'barnburger'})
        self.assertEqual(url, '/foodtrucks/barnburger/dashboard/kpis/')
        self.assertEqual(resolve(url).func.view_class, views.DashboardKpiAPIView)
