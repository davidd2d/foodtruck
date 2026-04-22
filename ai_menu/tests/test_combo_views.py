from decimal import Decimal

from django.test import TestCase
from django.urls import reverse

from foodtrucks.tests.factories import FoodTruckFactory, TaxFactory, UserFactory
from menu.models import Combo
from menu.tests.factories import CategoryFactory, ComboFactory, ComboItemFactory, ItemFactory, MenuFactory


class AIComboOwnerViewsTests(TestCase):
    def setUp(self):
        self.owner = UserFactory(is_foodtruck_owner=True)
        self.other_user = UserFactory(is_foodtruck_owner=True)
        self.foodtruck = FoodTruckFactory(owner=self.owner, name='Alpha Truck', price_display_mode='tax_excluded')
        self.menu = MenuFactory(food_truck=self.foodtruck, name='Main Menu')
        self.category = CategoryFactory(menu=self.menu, name='Combos')
        self.drinks_category = CategoryFactory(menu=self.menu, name='Drinks')
        self.alt_tax = TaxFactory(name='TVA 20%', rate=Decimal('0.2000'), is_default=False)
        self.item = ItemFactory(category=self.category, name='Classic Burger', base_price=Decimal('10.00'))
        self.combo = ComboFactory(category=self.category, name='Lunch Combo', combo_price=Decimal('14.00'))
        self.combo_item = ComboItemFactory(combo=self.combo, item=self.item, display_name='Classic Burger')

    def test_owner_can_view_combo_list(self):
        self.client.force_login(self.owner)

        response = self.client.get(reverse('ai_menu:combo-list', kwargs={'slug': self.foodtruck.slug}))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Lunch Combo')
        self.assertContains(response, 'Add combo')
        self.assertContains(response, reverse('ai_menu:combo-create', kwargs={'slug': self.foodtruck.slug}))

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
                'discount_amount': '2.00',
                'is_available': 'on',
                'display_order': '2',
                'combo_items-TOTAL_FORMS': '2',
                'combo_items-INITIAL_FORMS': '1',
                'combo_items-MIN_NUM_FORMS': '0',
                'combo_items-MAX_NUM_FORMS': '1000',
                'combo_items-0-id': str(self.combo_item.id),
                'combo_items-0-display_name': 'Burger updated',
                'combo_items-0-source_category': str(self.category.id),
                'combo_items-0-item': str(self.item.id),
                'combo_items-0-quantity': '2',
                'combo_items-0-display_order': '0',
                'combo_items-1-id': '',
                'combo_items-1-display_name': 'Drink',
                'combo_items-1-source_category': str(self.drinks_category.id),
                'combo_items-1-item': '',
                'combo_items-1-quantity': '1',
                'combo_items-1-display_order': '1',
            },
        )

        self.assertEqual(response.status_code, 302)
        self.combo.refresh_from_db()
        self.assertEqual(self.combo.name, 'Lunch Combo Deluxe')
        self.assertEqual(self.combo.combo_price, Decimal('16.50'))
        self.assertEqual(self.combo.discount_amount, Decimal('2.00'))
        self.assertEqual(self.combo.combo_items.count(), 2)
        self.assertTrue(self.combo.combo_items.filter(display_name='Drink', item__isnull=True, source_category=self.drinks_category).exists())

    def test_non_owner_cannot_edit_combo(self):
        self.client.force_login(self.other_user)

        response = self.client.get(reverse('ai_menu:combo-edit', kwargs={'slug': self.foodtruck.slug, 'combo_id': self.combo.id}))

        self.assertEqual(response.status_code, 404)

    def test_owner_can_create_combo_from_create_page(self):
        self.client.force_login(self.owner)

        response = self.client.post(
            reverse('ai_menu:combo-create', kwargs={'slug': self.foodtruck.slug}),
            {
                'category': str(self.category.id),
                'name': 'Combo Aperitivo',
                'description': 'Aperitivo combo',
                'tax': '',
                'combo_price': '18.00',
                'discount_amount': '2.50',
                'is_available': 'on',
                'display_order': '3',
            },
        )

        self.assertEqual(response.status_code, 302)
        created_combo = Combo.objects.get(name='Combo Aperitivo', category=self.category)
        self.assertEqual(created_combo.combo_price, Decimal('18.00'))
        self.assertEqual(created_combo.discount_amount, Decimal('2.50'))
        self.assertIn(
            reverse('ai_menu:combo-edit', kwargs={'slug': self.foodtruck.slug, 'combo_id': created_combo.id}),
            response['Location'],
        )

    def test_combo_edit_shows_ttc_labels_when_foodtruck_is_ttc(self):
        self.foodtruck.price_display_mode = self.foodtruck.PriceDisplayMode.TAX_INCLUDED
        self.foodtruck.save(update_fields=['price_display_mode'])
        self.client.force_login(self.owner)

        response = self.client.get(reverse('ai_menu:combo-edit', kwargs={'slug': self.foodtruck.slug, 'combo_id': self.combo.id}))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Combo price (TTC)')
        self.assertContains(response, 'Displayed prices are TTC')

    def test_combo_edit_converts_ttc_price_and_discount_to_ht_storage(self):
        self.foodtruck.price_display_mode = self.foodtruck.PriceDisplayMode.TAX_INCLUDED
        self.foodtruck.save(update_fields=['price_display_mode'])
        self.client.force_login(self.owner)

        response = self.client.post(
            reverse('ai_menu:combo-edit', kwargs={'slug': self.foodtruck.slug, 'combo_id': self.combo.id}),
            {
                'name': 'Lunch Combo Deluxe',
                'description': 'Updated combo',
                'tax': str(self.alt_tax.id),
                'combo_price': '24.00',
                'discount_amount': '3.60',
                'is_available': 'on',
                'display_order': '2',
                'combo_items-TOTAL_FORMS': '1',
                'combo_items-INITIAL_FORMS': '1',
                'combo_items-MIN_NUM_FORMS': '0',
                'combo_items-MAX_NUM_FORMS': '1000',
                'combo_items-0-id': str(self.combo_item.id),
                'combo_items-0-display_name': 'Burger updated',
                'combo_items-0-source_category': str(self.category.id),
                'combo_items-0-item': str(self.item.id),
                'combo_items-0-quantity': '1',
                'combo_items-0-display_order': '0',
            },
        )

        self.assertEqual(response.status_code, 302)
        self.combo.refresh_from_db()
        self.assertEqual(self.combo.combo_price, Decimal('20.00'))
        self.assertEqual(self.combo.discount_amount, Decimal('3.00'))

    def test_combo_list_displays_ttc_price_when_foodtruck_in_ttc_mode(self):
        self.foodtruck.price_display_mode = self.foodtruck.PriceDisplayMode.TAX_INCLUDED
        self.foodtruck.save(update_fields=['price_display_mode'])
        self.combo.tax = self.alt_tax
        self.combo.combo_price = Decimal('10.00')
        self.combo.save(update_fields=['tax', 'combo_price'])
        self.client.force_login(self.owner)

        response = self.client.get(reverse('ai_menu:combo-list', kwargs={'slug': self.foodtruck.slug}))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Displayed prices are TTC')
        self.assertContains(response, '€12.00')