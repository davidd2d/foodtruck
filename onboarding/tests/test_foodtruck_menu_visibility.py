from django.test import TestCase
from django.urls import reverse

from foodtrucks.tests.factories import FoodTruckFactory, PlanFactory
from menu.tests.factories import MenuFactory, CategoryFactory, ItemFactory


class FoodTruckMenuVisibilityTests(TestCase):
    def setUp(self):
        self.free_plan = PlanFactory(code='free', allows_ordering=False)
        self.foodtruck = FoodTruckFactory()
        self.foodtruck.subscription.plan = self.free_plan
        self.foodtruck.subscription.status = 'active'
        self.foodtruck.subscription.save()

        self.menu = MenuFactory(food_truck=self.foodtruck, is_active=True)
        CategoryFactory(menu=self.menu, name='Pasta')
        ItemFactory(name='Lasagnes', category=self.menu.categories.first())

    def _get_detail(self):
        return self.client.get(
            reverse('foodtrucks:foodtruck-detail', kwargs={'slug': self.foodtruck.slug})
        )

    def test_menu_panel_shows_for_free_plan(self):
        response = self._get_detail()
        self.assertEqual(response.status_code, 200)
        self.assertTrue(self.foodtruck.menus.exists())
        self.assertContains(response, '<div id="menu-container"')
        self.assertContains(response, 'Menu')
        self.assertContains(response, 'Ordering is not available for this foodtruck.')
        self.assertNotContains(response, 'Your cart')

    def test_ordering_disabled_for_free_plan(self):
        response = self._get_detail()
        self.assertContains(response, 'Ordering is not available for this foodtruck.')
        self.assertNotContains(response, 'Your cart')

    def test_ordering_enabled_for_pro_plan(self):
        pro_plan = PlanFactory(code='pro', allows_ordering=True)
        self.foodtruck.subscription.plan = pro_plan
        self.foodtruck.subscription.status = 'active'
        self.foodtruck.subscription.save()

        response = self._get_detail()
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'Ordering is not available for this foodtruck.')
        self.assertContains(response, 'Your cart')
