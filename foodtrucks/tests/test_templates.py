from django.test import TestCase
from django.urls import reverse

from foodtrucks.tests.factories import FoodTruckFactory, MenuFactory, CategoryFactory


class FoodTruckBrandingTemplateTests(TestCase):
    def setUp(self):
        self.foodtruck = FoodTruckFactory()
        self.menu = MenuFactory(food_truck=self.foodtruck)
        self.category = CategoryFactory(menu=self.menu, name='Aliments')

    def test_navbar_displays_logo_and_category_links(self):
        response = self.client.get(reverse('foodtrucks:foodtruck-detail', kwargs={'slug': self.foodtruck.slug}))
        self.assertContains(response, self.foodtruck.name)
        self.assertContains(response, 'id="foodtruck-title"')
        self.assertContains(response, 'category-nav')
        self.assertContains(response, self.category.name)
        self.assertContains(response, f'background-color: {self.foodtruck.get_primary_color()}')

    def test_fallback_secondary_color_without_logo(self):
        self.foodtruck.logo = None
        self.foodtruck.save(update_fields=['logo'])
        response = self.client.get(reverse('foodtrucks:foodtruck-detail', kwargs={'slug': self.foodtruck.slug}))
        self.assertNotContains(response, '<img src=')
        self.assertContains(response, f'background-color: {self.foodtruck.get_secondary_color()}')

    def test_user_menu_links_when_authenticated(self):
        self.client.login(email=self.foodtruck.owner.email, password='password123')
        response = self.client.get(reverse('foodtrucks:foodtruck-detail', kwargs={'slug': self.foodtruck.slug}))
        self.assertContains(response, reverse('accounts:profile'))
        self.assertContains(response, reverse('orders:history'))
        self.assertContains(response, reverse('accounts:logout'))

    def test_user_menu_shows_login_when_anonymous(self):
        response = self.client.get(reverse('foodtrucks:foodtruck-detail', kwargs={'slug': self.foodtruck.slug}))
        self.assertContains(response, reverse('accounts:login'))
