# Fixtures for onboarding tests

import json
from unittest.mock import MagicMock
from django.test import TestCase
from django.contrib.auth import get_user_model
from onboarding.models import OnboardingImport
from foodtrucks.tests.factories import UserFactory

User = get_user_model()


class OnboardingTestFixtures(TestCase):
    """Base class with common test fixtures for onboarding tests."""

    def setUp(self):
        self.user = UserFactory()
        
        # Create test preferences
        from preferences.models import Preference
        Preference.objects.get_or_create(name="Vegan")
        Preference.objects.get_or_create(name="Gluten Free")
        
        self.valid_ai_response = json.dumps({
            "foodtruck": {
                "name": "Test Food Truck",
                "description": "A delicious food truck",
                "preferences": ["Vegan", "Gluten Free"]
            },
            "menu": [
                {
                    "category": "Main Courses",
                    "items": [
                        {
                            "name": "Vegan Burger",
                            "description": "Plant-based burger",
                            "price": "12.50"
                        },
                        {
                            "name": "Gluten Free Pizza",
                            "description": "Rice crust pizza",
                            "price": "15.00"
                        }
                    ]
                },
                {
                    "category": "Drinks",
                    "items": [
                        {
                            "name": "Smoothie",
                            "description": "Fresh fruit smoothie",
                            "price": "5.00"
                        }
                    ]
                }
            ],
            "branding": {
                "primary_color": "#FF6B35",
                "secondary_color": "#F7931E",
                "logo_url": "https://example.com/logo.png"
            }
        })

        self.partial_ai_response = json.dumps({
            "foodtruck": {
                "name": "Partial Truck"
                # Missing description and preferences
            },
            "menu": []  # Empty menu
        })

        self.malformed_ai_response = "This is not JSON at all"

        self.empty_ai_response = ""

        # Create a processed import instance
        self.processed_import = OnboardingImport.objects.create(
            user=self.user,
            raw_text="Sample menu text",
            status='completed',
            parsed_data=json.loads(self.valid_ai_response)
        )

    def get_mock_openai_service(self, response_text=None):
        """Helper to create a mocked OpenAI service."""
        mock_service = MagicMock()
        if response_text is not None:
            mock_service.generate.return_value = response_text
        else:
            mock_service.generate.return_value = self.valid_ai_response
        return mock_service
