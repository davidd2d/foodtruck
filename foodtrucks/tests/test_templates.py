from django.test import TestCase
from django.urls import reverse

from foodtrucks.tests.factories import FoodTruckFactory, MenuFactory, CategoryFactory, UserFactory


class FoodTruckBrandingTemplateTests(TestCase):
    def setUp(self):
        self.foodtruck = FoodTruckFactory()
        self.menu = MenuFactory(food_truck=self.foodtruck)
        self.category = CategoryFactory(menu=self.menu, name='Aliments')

    def test_navbar_displays_logo_and_category_links(self):
        response = self.client.get(reverse('foodtrucks:foodtruck-detail', kwargs={'slug': self.foodtruck.slug}))
        self.assertContains(response, self.foodtruck.name)
        self.assertContains(response, 'id="foodtruck-title"')
        self.assertContains(response, 'foodtruck-order-navbar')
        self.assertContains(response, 'id="nav-cart-link"')
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
        self.assertContains(response, 'foodtruck-account-submenu')
        self.assertContains(response, 'foodtruck-orders-submenu')
        self.assertContains(response, 'foodtruck-menu-submenu')
        self.assertContains(response, 'foodtruck-billing-submenu')
        self.assertContains(response, 'foodtruck-menu-badge')
        self.assertContains(response, 'OPS')
        self.assertContains(response, 'MEN')
        self.assertContains(response, 'EUR')
        self.assertContains(response, 'Owner space')
        self.assertContains(response, 'Operations')
        self.assertContains(response, 'Billing')
        self.assertContains(response, reverse('accounts:profile', kwargs={'slug': self.foodtruck.slug}))
        self.assertContains(response, reverse(
            'orders:ticket-list-page',
            kwargs={'slug': self.foodtruck.slug, 'user_id': self.foodtruck.owner.id},
        ))
        self.assertContains(response, reverse('orders:owner-ticket-list', kwargs={'slug': self.foodtruck.slug}))
        self.assertContains(response, reverse('foodtrucks:foodtruck-dashboard', kwargs={'slug': self.foodtruck.slug}))
        self.assertContains(
            response,
            f"{reverse('payment-accounting-export')}?start_date=",
        )
        self.assertContains(response, reverse('accounts:logout'))

    def test_customer_menu_hides_owner_sections(self):
        customer = UserFactory(password='password123')
        self.client.login(email=customer.email, password='password123')

        response = self.client.get(reverse('foodtrucks:foodtruck-detail', kwargs={'slug': self.foodtruck.slug}))

        self.assertContains(response, 'foodtruck-account-submenu')
        self.assertContains(response, 'Customer space')
        self.assertNotContains(response, 'foodtruck-orders-submenu')
        self.assertNotContains(response, 'foodtruck-menu-submenu')
        self.assertNotContains(response, 'foodtruck-billing-submenu')
        self.assertNotContains(response, 'Operations')

    def test_user_menu_shows_login_when_anonymous(self):
        response = self.client.get(reverse('foodtrucks:foodtruck-detail', kwargs={'slug': self.foodtruck.slug}))
        self.assertContains(response, reverse('accounts:login'))
