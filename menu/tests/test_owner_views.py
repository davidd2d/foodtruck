from decimal import Decimal
from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from foodtrucks.tests.factories import TaxFactory
from foodtrucks.tests.factories import FoodTruckFactory, UserFactory
from menu.models import Combo, Item, Menu, Option
from menu.services.menu_import_service import MenuImportService
from menu.tests.factories import CategoryFactory, ComboFactory, ItemFactory, MenuFactory, OptionFactory, OptionGroupFactory
from onboarding.models import OnboardingImport


class OwnerMenuViewsTests(TestCase):
    def setUp(self):
        self.owner = UserFactory(is_foodtruck_owner=True)
        self.foodtruck = FoodTruckFactory(owner=self.owner, name='Cucina', price_display_mode='tax_excluded')
        self.menu = MenuFactory(food_truck=self.foodtruck, is_active=True)
        self.category = CategoryFactory(menu=self.menu, name='Burgers')
        self.item = ItemFactory(category=self.category, name='Smash Burger', base_price=Decimal('11.50'), is_available=True)
        self.combo = ComboFactory(category=self.category, name='Menu Midi', combo_price=Decimal('14.90'), is_available=True)
        self.option_group = OptionGroupFactory(item=self.item, name='Extras')
        self.option = OptionFactory(group=self.option_group, name='Cheddar', price_modifier=Decimal('1.20'), is_available=True)
        self.alt_tax = TaxFactory(name='TVA 20%', rate=Decimal('0.2000'), is_default=False)
        self.client.force_login(self.owner)

    def test_owner_menu_dashboard_is_accessible(self):
        response = self.client.get(reverse('menu:dashboard', kwargs={'slug': self.foodtruck.slug}))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Catalogue et prix')
        self.assertContains(response, 'Importer une carte')

    def test_owner_can_update_item_price_and_availability(self):
        response = self.client.post(
            reverse('menu:update-item', kwargs={'slug': self.foodtruck.slug, 'item_id': self.item.id}),
            {
                'item-%d-base_price' % self.item.id: '12.90',
                'item-%d-tax' % self.item.id: '',
                'item-%d-is_available' % self.item.id: '',
            },
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.item.refresh_from_db()
        self.assertEqual(self.item.base_price, Decimal('12.90'))
        self.assertFalse(self.item.is_available)

    def test_owner_can_update_item_tax_from_catalog(self):
        response = self.client.post(
            reverse('menu:update-item', kwargs={'slug': self.foodtruck.slug, 'item_id': self.item.id}),
            {
                'item-%d-base_price' % self.item.id: '11.50',
                'item-%d-tax' % self.item.id: str(self.alt_tax.id),
                'item-%d-is_available' % self.item.id: 'on',
            },
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.item.refresh_from_db()
        self.assertEqual(self.item.tax_id, self.alt_tax.id)

    def test_owner_item_update_returns_json_for_autosave_requests(self):
        response = self.client.post(
            reverse('menu:update-item', kwargs={'slug': self.foodtruck.slug, 'item_id': self.item.id}),
            {
                'item-%d-base_price' % self.item.id: '13.20',
                'item-%d-tax' % self.item.id: str(self.alt_tax.id),
                'item-%d-is_available' % self.item.id: 'on',
            },
            HTTP_ACCEPT='application/json',
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )

        self.assertEqual(response.status_code, 200)
        self.assertJSONEqual(
            response.content,
            {
                'success': True,
                'item_id': self.item.id,
                'name': self.item.name,
                'base_price': '13.20',
                'is_available': True,
                'tax_label': str(self.alt_tax),
            },
        )

    def test_owner_combo_update_returns_json_for_autosave_requests(self):
        response = self.client.post(
            reverse('menu:update-combo', kwargs={'slug': self.foodtruck.slug, 'combo_id': self.combo.id}),
            {
                'combo-%d-combo_price' % self.combo.id: '16.40',
                'combo-%d-tax' % self.combo.id: str(self.alt_tax.id),
                'combo-%d-is_available' % self.combo.id: '',
            },
            HTTP_ACCEPT='application/json',
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )

        self.assertEqual(response.status_code, 200)
        self.assertJSONEqual(
            response.content,
            {
                'success': True,
                'combo_id': self.combo.id,
                'name': self.combo.name,
                'combo_price': '16.40',
                'is_available': False,
                'tax_label': str(self.alt_tax),
            },
        )

    def test_owner_option_update_returns_json_for_autosave_requests(self):
        response = self.client.post(
            reverse('menu:update-option', kwargs={'slug': self.foodtruck.slug, 'option_id': self.option.id}),
            {
                'option-%d-price_modifier' % self.option.id: '2.10',
                'option-%d-is_available' % self.option.id: 'on',
            },
            HTTP_ACCEPT='application/json',
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )

        self.assertEqual(response.status_code, 200)
        self.assertJSONEqual(
            response.content,
            {
                'success': True,
                'option_id': self.option.id,
                'name': self.option.name,
                'price_modifier': '2.10',
                'is_available': True,
            },
        )

    def test_owner_can_update_combo_price_and_availability(self):
        response = self.client.post(
            reverse('menu:update-combo', kwargs={'slug': self.foodtruck.slug, 'combo_id': self.combo.id}),
            {
                'combo-%d-combo_price' % self.combo.id: '15.50',
                'combo-%d-tax' % self.combo.id: '',
                'combo-%d-is_available' % self.combo.id: 'on',
            },
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.combo.refresh_from_db()
        self.assertEqual(self.combo.combo_price, Decimal('15.50'))
        self.assertTrue(self.combo.is_available)

    def test_owner_can_update_combo_tax_from_catalog(self):
        response = self.client.post(
            reverse('menu:update-combo', kwargs={'slug': self.foodtruck.slug, 'combo_id': self.combo.id}),
            {
                'combo-%d-combo_price' % self.combo.id: '14.90',
                'combo-%d-tax' % self.combo.id: str(self.alt_tax.id),
                'combo-%d-is_available' % self.combo.id: 'on',
            },
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.combo.refresh_from_db()
        self.assertEqual(self.combo.tax_id, self.alt_tax.id)

    def test_catalog_page_shows_options(self):
        response = self.client.get(reverse('menu:catalog', kwargs={'slug': self.foodtruck.slug}))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Extras')
        self.assertContains(response, 'Cheddar')
        self.assertContains(response, 'Produit lié')
        self.assertContains(response, 'Taxe héritée')

    def test_catalog_page_exposes_category_anchor_for_navbar(self):
        response = self.client.get(reverse('menu:catalog', kwargs={'slug': self.foodtruck.slug}))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, f'id="category-{self.category.id}"', html=False)
        self.assertContains(
            response,
            f'href="{reverse("menu:catalog", kwargs={"slug": self.foodtruck.slug})}#category-{self.category.id}"',
            html=False,
        )

    def test_owner_can_update_option_from_catalog(self):
        response = self.client.post(
            reverse('menu:update-option', kwargs={'slug': self.foodtruck.slug, 'option_id': self.option.id}),
            {
                'option-%d-price_modifier' % self.option.id: '1.80',
                'option-%d-is_available' % self.option.id: '',
            },
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.option.refresh_from_db()
        self.assertEqual(self.option.price_modifier, Decimal('1.80'))
        self.assertFalse(self.option.is_available)

    def test_catalog_shows_ttc_labels_when_prices_include_tax(self):
        self.foodtruck.price_display_mode = self.foodtruck.PriceDisplayMode.TAX_INCLUDED
        self.foodtruck.save(update_fields=['price_display_mode'])

        response = self.client.get(reverse('menu:catalog', kwargs={'slug': self.foodtruck.slug}))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Price (TTC)')
        self.assertContains(response, 'Displayed prices are TTC')

    def test_owner_item_update_converts_ttc_input_to_ht_storage(self):
        self.foodtruck.price_display_mode = self.foodtruck.PriceDisplayMode.TAX_INCLUDED
        self.foodtruck.save(update_fields=['price_display_mode'])

        self.client.post(
            reverse('menu:update-item', kwargs={'slug': self.foodtruck.slug, 'item_id': self.item.id}),
            {
                'item-%d-base_price' % self.item.id: '12.00',
                'item-%d-tax' % self.item.id: '',
                'item-%d-is_available' % self.item.id: 'on',
            },
            follow=True,
        )

        self.item.refresh_from_db()
        self.assertEqual(self.item.base_price, Decimal('10.91'))

    def test_owner_combo_update_converts_ttc_input_to_ht_storage(self):
        self.foodtruck.price_display_mode = self.foodtruck.PriceDisplayMode.TAX_INCLUDED
        self.foodtruck.save(update_fields=['price_display_mode'])

        self.client.post(
            reverse('menu:update-combo', kwargs={'slug': self.foodtruck.slug, 'combo_id': self.combo.id}),
            {
                'combo-%d-combo_price' % self.combo.id: '22.00',
                'combo-%d-tax' % self.combo.id: str(self.alt_tax.id),
                'combo-%d-is_available' % self.combo.id: 'on',
            },
            follow=True,
        )

        self.combo.refresh_from_db()
        self.assertEqual(self.combo.combo_price, Decimal('18.33'))

    @patch('menu.services.menu_import_service.PdfReader')
    @patch('menu.services.menu_import_service.AIOnboardingService.process_import')
    def test_owner_can_import_menu_from_pdf(self, mock_process_import, mock_pdf_reader):
        def _mark_completed(import_id):
            import_instance = OnboardingImport.objects.get(pk=import_id)
            import_instance.status = 'completed'
            import_instance.parsed_data = {
                'menu': [
                    {
                        'category': 'Imported',
                        'items': [
                            {'name': 'New Taco', 'description': 'Imported dish', 'price': '9.90'}
                        ],
                    }
                ]
            }
            import_instance.save(update_fields=['status', 'parsed_data'])

        mock_process_import.side_effect = _mark_completed
        mock_page = type('MockPage', (), {'extract_text': lambda self: 'Imported taco menu'})()
        mock_pdf_reader.return_value.pages = [mock_page]
        pdf_file = SimpleUploadedFile('menu.pdf', b'%PDF-1.4 test', content_type='application/pdf')

        response = self.client.post(
            reverse('menu:import', kwargs={'slug': self.foodtruck.slug}),
            {
                'raw_text': '',
                'source_url': '',
                'documents': pdf_file,
            },
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Catalogue and pricing')
        self.menu.refresh_from_db()
        self.assertFalse(self.menu.is_active)
        active_menu = Menu.objects.get(food_truck=self.foodtruck, is_active=True)
        self.assertTrue(Item.objects.filter(category__menu=active_menu, name='New Taco').exists())


class MenuImportServiceTests(TestCase):
    def test_apply_import_to_foodtruck_replaces_active_menu(self):
        owner = UserFactory(is_foodtruck_owner=True)
        foodtruck = FoodTruckFactory(owner=owner, name='Truck')
        previous_menu = MenuFactory(food_truck=foodtruck, is_active=True)
        previous_category = CategoryFactory(menu=previous_menu)
        ItemFactory(category=previous_category, name='Old item')
        import_instance = OnboardingImport.objects.create(
            user=owner,
            status='completed',
            parsed_data={
                'menu': [
                    {
                        'category': 'Pizza',
                        'items': [
                            {'name': 'Marinara', 'description': 'Tomato', 'price': '8.50'},
                        ],
                    }
                ]
            },
        )

        menu = MenuImportService().apply_import_to_foodtruck(foodtruck, import_instance)

        previous_menu.refresh_from_db()
        self.assertFalse(previous_menu.is_active)
        self.assertTrue(menu.is_active)
        self.assertTrue(Item.objects.filter(category__menu=menu, name='Marinara').exists())