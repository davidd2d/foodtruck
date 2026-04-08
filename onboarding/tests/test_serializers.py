import json
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from onboarding.models import OnboardingImport, OnboardingImage
from onboarding.api.serializers import OnboardingImportSerializer, OnboardingImageSerializer
from foodtrucks.tests.factories import UserFactory

User = get_user_model()


class OnboardingSerializerTests(TestCase):
    """Test serializer functionality."""

    def setUp(self):
        self.user = UserFactory()

    def test_onboarding_image_serializer(self):
        """Test OnboardingImageSerializer serializes correctly."""
        import_instance = OnboardingImport.objects.create(user=self.user, raw_text="Test")
        image_content = b"fake image content"
        image_file = ContentFile(image_content, name="test.jpg")
        onboarding_image = OnboardingImage.objects.create(
            import_instance=import_instance,
            image=image_file
        )

        serializer = OnboardingImageSerializer(onboarding_image)
        data = serializer.data

        self.assertIn('id', data)
        self.assertIn('url', data)
        self.assertIn('created_at', data)
        self.assertTrue(data['url'].startswith('/media/'))
        self.assertIn(f"/onboarding/user_{self.user.id}/import_{import_instance.id}/raw/", data['url'])

    def test_onboarding_import_serializer_with_images(self):
        """Test OnboardingImportSerializer handles images correctly."""
        import_instance = OnboardingImport.objects.create(user=self.user, raw_text="Test menu")

        # Create test images
        image_content = b"fake image content"
        image_file1 = ContentFile(image_content, name="test1.jpg")
        image_file2 = ContentFile(image_content, name="test2.jpg")

        OnboardingImage.objects.create(import_instance=import_instance, image=image_file1)
        OnboardingImage.objects.create(import_instance=import_instance, image=image_file2)

        serializer = OnboardingImportSerializer(import_instance)
        data = serializer.data

        # Check basic fields
        self.assertEqual(data['id'], import_instance.id)
        self.assertEqual(data['raw_text'], "Test menu")
        self.assertEqual(data['status'], 'pending')

        # Check images
        self.assertIn('images', data)
        self.assertEqual(len(data['images']), 2)

        # Check image data structure
        image_data = data['images'][0]
        self.assertIn('id', image_data)
        self.assertIn('url', image_data)
        self.assertIn('created_at', image_data)

    def test_onboarding_import_serializer_without_images(self):
        """Test OnboardingImportSerializer handles empty images correctly."""
        import_instance = OnboardingImport.objects.create(user=self.user, raw_text="Test menu")

        serializer = OnboardingImportSerializer(import_instance)
        data = serializer.data

        # Check images is empty list
        self.assertIn('images', data)
        self.assertEqual(data['images'], [])

    def test_serializer_no_crash_with_many_related_manager(self):
        """Test that serializer doesn't crash when accessing images relation."""
        import_instance = OnboardingImport.objects.create(user=self.user, raw_text="Test")

        # This should not crash - the serializer should handle the ManyRelatedManager properly
        serializer = OnboardingImportSerializer(import_instance)
        data = serializer.data

        # Should have images field as empty list
        self.assertEqual(data['images'], [])
