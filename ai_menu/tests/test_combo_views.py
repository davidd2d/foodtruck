from decimal import Decimal

from django.test import TestCase
from django.urls import reverse

from foodtrucks.tests.factories import FoodTruckFactory, UserFactory
from menu.tests.factories import CategoryFactory, ComboFactory, ComboItemFactory, ItemFactory, MenuFactory


class AIComboOwnerViewsTests(TestCase):
    def setUp(self):
        self.owner = UserFactory(is_foodtruck_owner=True)
        self.other_user = UserFactory(is_foodtruck_owner=True)
        self.foodtruck = FoodTruckFactory(owner=self.owner, name='Alpha Truck')
        self.menu = MenuFactory(food_truck=self.foodtruck, name='Main Menu')
        self.category = CategoryFactory(menu=self.menu, name='Combos')
        self.item = ItemFactory(category=self.category, name='Classic Burger', base_price=Decimal('10.00'))
        self.combo = ComboFactory(category=self.category, name='Lunch Combo', combo_price=Decimal('14.00'))
        self.combo_item = ComboItemFactory(combo=self.combo, item=self.item, display_name='Classic Burger')

    def test_owner_can_view_combo_list(self):
        self.client.force_login(self.owner)

        response = self.client.get(reverse('ai_menu:combo-list', kwargs={'slug': self.foodtruck.slug}))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Lunch Combo')

    def test_non_owner_cannot_view_combo_list(self):
        self.client.force_login(self.other_user)

        response = self.client.get(reverse('ai_menu:combo-list', kwargs={'slug': self.foodtruck.slug}))

        self.assertEqual(response.status_code, 404)

    def test_owner_can_edit_combo_and_components(self):
        self.client.force_login(self.owner)

        response = self.client.post(
            reverse('ai_menu:combo-edit', kwargs={'slug': self.foodtruck.slug, 'combo_id': self.combo.id}),
            {
                'name': 'Lunch Combo Deluxe',
                'description': 'Updated combo',
                'combo_price': '16.50',
                'is_available': 'on',
                'display_order': '2',
                'combo_items-TOTAL_FORMS': '2',
                'combo_items-INITIAL_FORMS': '1',
                'combo_items-MIN_NUM_FORMS': '0',
                'combo_items-MAX_NUM_FORMS': '1000',
                'combo_items-0-id': str(self.combo_item.id),
                'combo_items-0-display_name': 'Burger updated',
                'combo_items-0-item': str(self.item.id),
                'combo_items-0-quantity': '2',
                'combo_items-0-display_order': '0',
                'combo_items-1-id': '',
                'combo_items-1-display_name': 'Drink',
                'combo_items-1-item': '',
                'combo_items-1-quantity': '1',
                'combo_items-1-display_order': '1',
            },
        )

        self.assertEqual(response.status_code, 302)
        self.combo.refresh_from_db()
        self.assertEqual(self.combo.name, 'Lunch Combo Deluxe')
        self.assertEqual(self.combo.combo_price, Decimal('16.50'))
        self.assertEqual(self.combo.combo_items.count(), 2)
        self.assertTrue(self.combo.combo_items.filter(display_name='Drink', item__isnull=True).exists())

    def test_non_owner_cannot_edit_combo(self):
        self.client.force_login(self.other_user)

        response = self.client.get(reverse('ai_menu:combo-edit', kwargs={'slug': self.foodtruck.slug, 'combo_id': self.combo.id}))

        self.assertEqual(response.status_code, 404)