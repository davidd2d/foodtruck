import json
from decimal import Decimal
from unittest.mock import patch, MagicMock
from django.test import TestCase
from django.contrib.auth import get_user_model
from onboarding.models import OnboardingImport
from onboarding.services.ai_onboarding import AIOnboardingService
from foodtrucks.tests.factories import UserFactory

User = get_user_model()


class AIOnboardingServiceTests(TestCase):
    def setUp(self):
        self.user = UserFactory()
        self._service = None

    @property
    def service(self):
        if self._service is None:
            self._service = AIOnboardingService()
        return self._service

    @patch('onboarding.services.ai_onboarding.OpenAIService')
    def test_process_import_handles_valid_json_response(self, mock_openai_class):
        # Mock OpenAI service
        mock_openai = MagicMock()
        mock_openai.generate.return_value = json.dumps({
            "foodtruck": {
                "name": "Test Truck",
                "description": "A test food truck",
                "preferences": ["Vegan"]
            },
            "menu": [
                {
                    "category": "Main",
                    "items": [
                        {
                            "name": "Burger",
                            "price": "10.50",
                            "description": "Delicious burger"
                        }
                    ]
                }
            ],
            "branding": {
                "primary_color": "#FF0000",
                "secondary_color": "#00FF00"
            }
        })
        mock_openai_class.return_value = mock_openai

        # Create import instance
        import_instance = OnboardingImport.objects.create(
            user=self.user,
            raw_text="Sample menu text"
        )

        # Process import
        result = self.service.process_import(import_instance.id)

        # Refresh from DB
        import_instance.refresh_from_db()

        # Assertions
        self.assertEqual(result['status'], 'success')
        self.assertEqual(import_instance.status, 'completed')
        self.assertIn('foodtruck', import_instance.parsed_data)
        self.assertIn('menu', import_instance.parsed_data)
        self.assertIn('branding', import_instance.parsed_data)

    @patch('onboarding.services.ai_onboarding.OpenAIService.generate')
    def test_process_import_handles_malformed_json(self, mock_generate):
        # Mock OpenAI service with invalid JSON
        mock_generate.return_value = "Invalid JSON response"

        import_instance = OnboardingImport.objects.create(
            user=self.user,
            raw_text="Sample text"
        )

        result = self.service.process_import(import_instance.id)
        import_instance.refresh_from_db()

        self.assertEqual(result['status'], 'success')
        self.assertEqual(import_instance.status, 'completed')
        self.assertEqual(import_instance.parsed_data, self.service._get_empty_structure())  # Empty structure

    @patch('onboarding.services.ai_onboarding.OpenAIService.generate')
    def test_process_import_handles_empty_response(self, mock_generate):
        # Mock OpenAI service with empty response
        mock_generate.return_value = ""

        import_instance = OnboardingImport.objects.create(
            user=self.user,
            raw_text="Sample text"
        )

        result = self.service.process_import(import_instance.id)
        import_instance.refresh_from_db()

        self.assertEqual(result['status'], 'success')
        self.assertEqual(import_instance.status, 'completed')
        self.assertEqual(import_instance.parsed_data, self.service._get_empty_structure())

    @patch('onboarding.services.ai_onboarding.OpenAIService.generate')
    def test_process_import_handles_partial_data(self, mock_generate):
        # Mock OpenAI service with partial data
        mock_generate.return_value = json.dumps({
            "foodtruck": {
                "name": "Test Truck"
                # Missing description, preferences
            },
            "menu": []  # Empty menu
        })

        import_instance = OnboardingImport.objects.create(
            user=self.user,
            raw_text="Sample text"
        )

        result = self.service.process_import(import_instance.id)
        import_instance.refresh_from_db()

        self.assertEqual(result['status'], 'success')
        self.assertEqual(import_instance.status, 'completed')
        self.assertIn('foodtruck', import_instance.parsed_data)
        self.assertEqual(import_instance.parsed_data['foodtruck']['name'], 'Test Truck')

    @patch('onboarding.services.ai_onboarding.OpenAIService')
    def test_process_import_status_transitions(self, mock_openai_class):
        mock_openai = MagicMock()
        mock_openai.generate.return_value = json.dumps({
            "foodtruck": {"name": "Test"},
            "menu": [],
            "branding": {}
        })
        mock_openai_class.return_value = mock_openai

        import_instance = OnboardingImport.objects.create(
            user=self.user,
            raw_text="Sample text"
        )

        # Initially pending
        self.assertEqual(import_instance.status, 'pending')

        result = self.service.process_import(import_instance.id)

        import_instance.refresh_from_db()
        self.assertEqual(import_instance.status, 'completed')

    @patch('onboarding.services.ai_onboarding.OpenAIService')
    def test_process_import_handles_ai_failure(self, mock_openai_class):
        # Mock OpenAI service to raise exception
        mock_openai = MagicMock()
        mock_openai.generate.side_effect = Exception("AI service error")
        mock_openai_class.return_value = mock_openai

        import_instance = OnboardingImport.objects.create(
            user=self.user,
            raw_text="Sample text"
        )

        result = self.service.process_import(import_instance.id)
        import_instance.refresh_from_db()

        self.assertEqual(result['status'], 'error')  # Service marks failure on critical errors
        self.assertEqual(import_instance.status, 'failed')

    def test_normalize_preferences_maps_to_existing(self):
        from preferences.models import Preference
        # Create some preferences
        vegan_pref = Preference.objects.create(name="Vegan")
        gluten_free_pref = Preference.objects.create(name="Gluten Free")

        preferences = ["vegan", "gluten-free", "non-existent"]
        normalized = self.service._normalize_preferences(preferences)

        self.assertIn("Vegan", normalized)
        self.assertIn("Gluten Free", normalized)
        self.assertIn("non-existent", normalized)  # Keep unknown preferences

    def test_normalize_price_handles_various_formats(self):
        # Test different price formats
        price, _ = self.service._normalize_price("10.50")
        self.assertEqual(price, Decimal("10.50"))
        price, _ = self.service._normalize_price("€10.50")
        self.assertEqual(price, Decimal("10.50"))
        price, _ = self.service._normalize_price("$10")
        self.assertEqual(price, Decimal("10.00"))
        price, _ = self.service._normalize_price("10")
        self.assertEqual(price, Decimal("10.00"))

    def test_price_parsing_and_validation_handles_commas(self):
        price, corrected = self.service._normalize_price("8,90€")
        self.assertEqual(price, Decimal("8.90"))
        self.assertFalse(corrected)

    def test_price_correction_for_missing_decimal(self):
        price, corrected = self.service._normalize_price("890")
        self.assertEqual(price, Decimal("8.90"))
        self.assertTrue(corrected)

    def test_extreme_price_corrects_or_logs(self):
        price, corrected = self.service._normalize_price("120")
        self.assertEqual(price, Decimal("1.20"))
        self.assertTrue(corrected)

    def test_logo_colors_override_other_sources(self):
        text_data = {
            "foodtruck": {"name": "Text Truck"},
            "menu": [],
            "branding": {"primary_color": {"name": "pale", "hex": ""}, "secondary_color": "#111111"}
        }
        menu_data = {
            "foodtruck": {},
            "menu": [],
            "branding": {"primary_color": "#222222", "secondary_color": "#333333"}
        }

        logo_data = {
            "branding": {"primary_color": "#ABCDEF", "secondary_color": "#123456"}
        }

        merged = self.service._merge_data(text_data, menu_data, logo_data)

        self.assertEqual(merged['branding']['primary_color'], '#ABCDEF')
        self.assertEqual(merged['branding']['secondary_color'], '#123456')

    def test_generate_foodtruck_fallback_is_localized(self):
        fallback = self.service._get_fallback_foodtruck('tacos', language_code='es')

        self.assertEqual(fallback['foodtruck']['language_code'], 'es')
        self.assertEqual(fallback['menu'][0]['category'], 'Platos principales')

    def test_generate_foodtruck_prompt_includes_target_language(self):
        prompt = self.service._build_foodtruck_generation_prompt('burger gourmet', 'fr')

        self.assertIn('Write all food truck, category and item content in French', prompt)
        self.assertIn('"language_code": "fr"', prompt)

    def test_normalize_colors_maps_names_and_hex(self):
        branding = {
            'primary_color': 'dark red',
            'secondary_color': {'name': 'beige', 'hex': ''},
            'style': 'Vintage'
        }

        colors = self.service.normalize_colors(branding)

        self.assertEqual(colors['primary_color'], '#8B0000')
        self.assertEqual(colors['secondary_color'], '#F5F5DC')
        self.assertEqual(colors['style'], 'Vintage')

    def test_normalize_colors_invalid_values_fallback_defaults(self):
        branding = {
            'primary_color': '#GGGGGG',
            'secondary_color': 'mystery color'
        }

        colors = self.service.normalize_colors(branding)

        self.assertEqual(colors['primary_color'], self.service.DEFAULT_PRIMARY_COLOR)
        self.assertEqual(colors['secondary_color'], self.service.DEFAULT_SECONDARY_COLOR)

    def test_merge_data_combines_text_and_image(self):
        text_data = {
            "foodtruck": {"name": "Truck A"},
            "menu": [{"category": "Main", "items": [{"name": "Burger"}]}]
        }
        image_data = {
            "menu": [{"category": "Main", "items": [{"name": "Fries"}]}],
            "branding": {"color": "red"}
        }

        merged = self.service._merge_data(text_data, image_data)

        self.assertEqual(merged["foodtruck"]["name"], "Truck A")
        self.assertEqual(len(merged["menu"][0]["items"]), 2)  # Burger and Fries
        self.assertEqual(merged["branding"]["color"], "red")
