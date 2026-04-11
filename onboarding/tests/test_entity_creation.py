import json
from unittest.mock import patch, MagicMock
from django.test import TestCase, TransactionTestCase
from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from onboarding.models import OnboardingImport, OnboardingImage
from onboarding.services.ai_onboarding import AIOnboardingService
from onboarding.tests.fixtures import OnboardingTestFixtures
from foodtrucks.models import FoodTruck
from menu.models import Menu, Category, Item
from preferences.models import Preference


class EntityCreationTests(OnboardingTestFixtures):
    """Test entity creation from processed imports."""

    @patch('onboarding.services.ai_onboarding.OpenAIService')
    def test_create_foodtruck_from_import_full_data(self, mock_openai_class):
        mock_openai_class.return_value = self.get_mock_openai_service()

        service = AIOnboardingService()
        result = service.create_foodtruck_from_import(self.processed_import)

        # Check FoodTruck created
        foodtruck = FoodTruck.objects.get(name="Test Food Truck")
        self.assertEqual(foodtruck.default_language, 'en')
        self.assertEqual(foodtruck.description, "A delicious food truck")
        self.assertEqual(foodtruck.primary_color, "#FF6B35")
        self.assertEqual(foodtruck.secondary_color, "#F7931E")

        # Check Menu created
        menu = Menu.objects.get(food_truck=foodtruck)
        self.assertEqual(menu.name, "Test Food Truck Menu")

        # Check Categories and Items
        main_category = Category.objects.get(menu=menu, name="Main Courses")
        drinks_category = Category.objects.get(menu=menu, name="Drinks")

        vegan_burger = Item.objects.get(category=main_category, name="Vegan Burger")
        self.assertEqual(float(vegan_burger.base_price), 12.50)

        smoothie = Item.objects.get(category=drinks_category, name="Smoothie")
        self.assertEqual(float(smoothie.base_price), 5.00)

        # Check Preferences
        vegan_pref = Preference.objects.get(name="Vegan")
        gluten_free_pref = Preference.objects.get(name="Gluten Free")
        self.assertIn(vegan_pref, foodtruck.supported_preferences.all())
        self.assertIn(gluten_free_pref, foodtruck.supported_preferences.all())

    @patch('onboarding.services.ai_onboarding.OpenAIService')
    def test_create_foodtruck_from_import_partial_data(self, mock_openai_class):
        # Use partial data
        partial_import = OnboardingImport.objects.create(
            user=self.user,
            raw_text="Partial data",
            status='completed',
            parsed_data=json.loads(self.partial_ai_response)
        )

        service = AIOnboardingService()
        result = service.create_foodtruck_from_import(partial_import)

        # Should still create FoodTruck with available data
        foodtruck = FoodTruck.objects.get(name="Partial Truck")
        self.assertEqual(foodtruck.default_language, 'en')
        self.assertEqual(foodtruck.description, "")  # Default empty

        # Should create empty menu
        menu = Menu.objects.get(food_truck=foodtruck)
        self.assertEqual(Category.objects.filter(menu=menu).count(), 0)

    @patch('onboarding.services.ai_onboarding.OpenAIService')
    def test_create_foodtruck_from_import_handles_duplicate_names(self, mock_openai_class):
        # Create first foodtruck
        service = AIOnboardingService()
        service.create_foodtruck_from_import(self.processed_import)

        # Try to create another with same name
        duplicate_import = OnboardingImport.objects.create(
            user=self.user,
            raw_text="Duplicate",
            status='completed',
            parsed_data=json.loads(self.valid_ai_response)
        )

        result = service.create_foodtruck_from_import(duplicate_import)

        # Should create with modified name
        foodtrucks = FoodTruck.objects.filter(name__startswith="Test Food Truck")
        self.assertEqual(foodtrucks.count(), 2)

    def test_create_foodtruck_from_import_requires_completed_status(self):
        pending_import = OnboardingImport.objects.create(
            user=self.user,
            raw_text="Pending",
            status='pending'
        )

        service = AIOnboardingService()
        with self.assertRaises(ValidationError):
            service.create_foodtruck_from_import(pending_import)

    @patch('onboarding.services.ai_onboarding.OpenAIService')
    def test_create_foodtruck_from_import_normalizes_prices(self, mock_openai_class):
        # Test price normalization during creation
        price_variations = json.dumps({
            "foodtruck": {"name": "Price Test Truck"},
            "menu": [
                {
                    "category": "Test",
                    "items": [
                        {"name": "Item1", "price": "€10.50"},
                        {"name": "Item2", "price": "$15"},
                        {"name": "Item3", "price": "20"}
                    ]
                }
            ],
            "branding": {}
        })

        price_import = OnboardingImport.objects.create(
            user=self.user,
            raw_text="Price test",
            status='completed',
            parsed_data=json.loads(price_variations)
        )

        service = AIOnboardingService()
        service.create_foodtruck_from_import(price_import)

        foodtruck = FoodTruck.objects.get(name="Price Test Truck")
        menu = Menu.objects.get(food_truck=foodtruck)
        category = Category.objects.get(menu=menu)

        item1 = Item.objects.get(category=category, name="Item1")
        item2 = Item.objects.get(category=category, name="Item2")
        item3 = Item.objects.get(category=category, name="Item3")

        self.assertEqual(float(item1.base_price), 10.50)
        self.assertEqual(float(item2.base_price), 15.00)
        self.assertEqual(float(item3.base_price), 20.00)

    def test_create_foodtruck_from_import_uses_detected_language(self):
        language_import = OnboardingImport.objects.create(
            user=self.user,
            raw_text="French content",
            status='completed',
            parsed_data={
                'foodtruck': {
                    'language_code': 'fr',
                    'name': 'Camion Test',
                    'description': 'Cuisine de rue',
                },
                'menu': [],
                'branding': {},
            }
        )

        service = AIOnboardingService()
        service.create_foodtruck_from_import(language_import)

        foodtruck = FoodTruck.objects.get(name='Camion Test')
        menu = Menu.objects.get(food_truck=foodtruck)

        self.assertEqual(foodtruck.default_language, 'fr')
        self.assertEqual(menu.name, 'Camion Test Carte')


class ResilienceTests(OnboardingTestFixtures):
    """Test system resilience under various failure conditions."""

    @patch('onboarding.services.ai_onboarding.OpenAIService')
    def test_process_import_handles_large_input(self, mock_openai_class):
        # Create large input text
        large_text = "Menu item " * 1000  # 11,000 characters
        mock_openai_class.return_value = self.get_mock_openai_service()

        import_instance = OnboardingImport.objects.create(
            user=self.user,
            raw_text=large_text
        )

        service = AIOnboardingService()
        result = service.process_import(import_instance.id)

        import_instance.refresh_from_db()
        self.assertEqual(import_instance.status, 'completed')

    @patch('onboarding.services.ai_onboarding.OpenAIService')
    def test_process_import_handles_timeout_simulation(self, mock_openai_class):
        # Simulate timeout by making generate() slow or raise exception
        mock_openai = MagicMock()
        mock_openai.generate.side_effect = Exception("Timeout")
        mock_openai_class.return_value = mock_openai

        import_instance = OnboardingImport.objects.create(
            user=self.user,
            raw_text="Test"
        )

        service = AIOnboardingService()
        result = service.process_import(import_instance.id)

        import_instance.refresh_from_db()
        self.assertEqual(import_instance.status, 'failed')
        self.assertEqual(result['status'], 'error')

    @patch('onboarding.services.ai_onboarding.OpenAIService')
    def test_process_import_handles_empty_raw_text(self, mock_openai_class):
        mock_openai_class.return_value = self.get_mock_openai_service()

        import_instance = OnboardingImport.objects.create(
            user=self.user,
            raw_text=""  # Empty text
        )

        service = AIOnboardingService()
        result = service.process_import(import_instance.id)

        import_instance.refresh_from_db()
        self.assertEqual(import_instance.status, 'completed')
        # Should still process with empty structure

    @patch('onboarding.services.ai_onboarding.OpenAIService')
    def test_process_import_handles_only_images(self, mock_openai_class):
        mock_openai_class.return_value = self.get_mock_openai_service()

        import_instance = OnboardingImport.objects.create(
            user=self.user,
            raw_text="",  # No text
        )
        OnboardingImage.objects.create(import_instance=import_instance, image=ContentFile(b"menu", name="menu.jpg"))
        OnboardingImage.objects.create(import_instance=import_instance, image=ContentFile(b"logo", name="logo.jpg"))

        service = AIOnboardingService()
        result = service.process_import(import_instance.id)

        import_instance.refresh_from_db()
        self.assertEqual(import_instance.status, 'completed')
