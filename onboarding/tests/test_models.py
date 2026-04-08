import json
from unittest.mock import patch, MagicMock
from django.test import TestCase
from django.contrib.auth import get_user_model
from onboarding.models import OnboardingImport
from onboarding.services.ai_onboarding import AIOnboardingService
from foodtrucks.tests.factories import UserFactory

User = get_user_model()


class OnboardingImportModelTests(TestCase):
    def setUp(self):
        self.user = UserFactory()

    def test_onboarding_import_creation(self):
        import_instance = OnboardingImport.objects.create(
            user=self.user,
            raw_text="Sample text",
            source_url="https://example.com"
        )
        self.assertEqual(import_instance.status, 'pending')
        self.assertEqual(import_instance.parsed_data, {})
        self.assertEqual(import_instance.user, self.user)

    def test_onboarding_import_str_representation(self):
        import_instance = OnboardingImport.objects.create(
            user=self.user,
            raw_text="Sample text"
        )
        expected_str = f"Onboarding Import for {self.user.email} - pending"
        self.assertEqual(str(import_instance), expected_str)
