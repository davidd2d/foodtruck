import json
import os
import tempfile
from decimal import Decimal
from unittest.mock import patch, MagicMock
from django.test import TestCase, override_settings
from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from onboarding.models import OnboardingImport, OnboardingImage
from onboarding.services.ai_onboarding import AIOnboardingService
from foodtrucks.tests.factories import UserFactory

User = get_user_model()


class AIOnboardingImageTests(TestCase):
    def setUp(self):
        self.user = UserFactory()
        self.service = AIOnboardingService()

    @patch('onboarding.services.ai_onboarding.OpenAIService.generate_with_images')
    @patch('onboarding.services.ai_onboarding.AIOnboardingService._encode_image_to_base64', return_value='fake_base64_data')
    @patch('os.path.exists', return_value=True)
    def test_analyze_images_extracts_prices_and_items(self, mock_exists, mock_encode, mock_generate_images):
        mock_generate_images.return_value = json.dumps({
            "menu": [
                {
                    "category": "Pasta",
                    "items": [
                        {
                            "name": "Lasagnes",
                            "description": "Cheesy layers",
                            "price": "12.50",
                            "currency": "€"
                        },
                        {
                            "name": "Spaghetti Bolognese",
                            "description": "Rich meat sauce",
                            "price": "11",
                            "currency": "€"
                        }
                    ]
                }
            ],
            "branding": {
                "primary_color": "#D23A2C",
                "secondary_color": "#F7E3D2"
            }
        })

        mock_image = MagicMock()
        mock_image.image.path = "/fake/path/menu.jpg"
        menu_result, logo_result = self.service.analyze_images([mock_image], [])

        self.assertIn("menu", menu_result)
        self.assertEqual(len(menu_result["menu"]), 1)
        self.assertEqual(menu_result["menu"][0]["category"], "Pasta")
        self.assertEqual(menu_result["menu"][0]["items"][0]["price"], "12.50")
        self.assertEqual(menu_result["branding"]["primary_color"], "#D23A2C")
        self.assertEqual(logo_result, {})

    def test_merge_results_prioritizes_image_prices_and_keeps_text_descriptions(self):
        text_data = {
            "foodtruck": {"cuisine_type": "American"},
            "menu": [
                {
                    "category": "Mains",
                    "items": [
                        {
                            "name": "Burger",
                            "description": "Tasty burger",
                            "price": None,
                            "currency": ""
                        }
                    ]
                }
            ]
        }
        image_data = {
            "menu": [
                {
                    "category": "Mains",
                    "items": [
                        {
                            "name": "burger",
                            "description": "",
                            "price": "9.99",
                            "currency": "$"
                        }
                    ]
                }
            ],
            "branding": {"primary_color": "#000000"}
        }

        merged = self.service._merge_data(text_data, image_data)
        self.assertEqual(len(merged["menu"]), 1)
        merged_item = merged["menu"][0]["items"][0]
        self.assertEqual(merged_item["price"], "9.99")
        self.assertEqual(merged_item["description"], "Tasty burger")
        self.assertEqual(merged_item["currency"], "$")

    def test_normalize_price_handles_messy_formats(self):
        price, _ = self.service._normalize_price("10€")
        self.assertEqual(price, Decimal("10"))
        price, _ = self.service._normalize_price("€10")
        self.assertEqual(price, Decimal("10"))
        price, _ = self.service._normalize_price("10.00")
        self.assertEqual(price, Decimal("10.00"))
        price, _ = self.service._normalize_price("$1,234.50")
        self.assertIsNone(price)

    @patch('onboarding.services.ai_onboarding.OpenAIService.generate_with_images')
    def test_full_pipeline_with_image_only_import(self, mock_generate_images):
        mock_generate_images.return_value = json.dumps({
            "menu": [
                {
                    "category": "Pizza",
                    "items": [
                        {
                            "name": "Margherita",
                            "description": "Tomato, mozzarella, basil",
                            "price": "12.50",
                            "currency": "€"
                        }
                    ]
                }
            ],
            "branding": {
                "primary_color": "#FF0000",
                "secondary_color": "#FFFFFF"
            }
        })

        import_instance = OnboardingImport.objects.create(
            user=self.user,
            raw_text="",
        )

        result = self.service.process_import(import_instance.id)
        import_instance.refresh_from_db()

        self.assertEqual(result["status"], "success")
        self.assertEqual(import_instance.status, "completed")
        self.assertIn("menu", import_instance.parsed_data)
        self.assertEqual(len(import_instance.parsed_data["menu"]), 0)  # No images, so empty menu

    @patch('onboarding.services.ai_onboarding.OpenAIService.generate_with_images')
    def test_edge_cases_empty_image_and_partial_menu(self, mock_generate_images):
        mock_generate_images.return_value = json.dumps({
            "menu": [
                {
                    "category": "Drinks",
                    "items": [
                        {
                            "name": "Water",
                            "description": "",
                            "price": None,
                            "currency": ""
                        }
                    ]
                }
            ],
            "branding": {
                "primary_color": "",
                "secondary_color": ""
            }
        })

        menu_result, logo_result = self.service.analyze_images([], [])
        self.assertEqual(menu_result, {})
        self.assertEqual(logo_result, {})

        import_instance = OnboardingImport.objects.create(
            user=self.user,
            raw_text="",
        )
        result = self.service.process_import(import_instance.id)
        import_instance.refresh_from_db()

        self.assertEqual(result["status"], "success")
        self.assertEqual(len(import_instance.parsed_data["menu"]), 0)  # No images, so empty menu


@override_settings(MEDIA_ROOT=tempfile.mkdtemp())
class OnboardingFileStorageTests(TestCase):
    """Test file upload and storage functionality."""

    def setUp(self):
        self.user = UserFactory()
        self.service = AIOnboardingService()

    def test_file_upload_creates_import_with_images(self):
        """Test that uploading images creates OnboardingImport with associated OnboardingImage instances."""
        import_instance = OnboardingImport.objects.create(user=self.user)

        # Create a test image file
        image_content = b"fake image content"
        image_file = ContentFile(image_content, name="test_menu.jpg")

        # Create OnboardingImage instance
        onboarding_image = OnboardingImage.objects.create(
            import_instance=import_instance,
            image=image_file
        )

        # Refresh from database
        import_instance.refresh_from_db()

        # Check that the image is associated
        self.assertEqual(import_instance.image_files.count(), 1)
        self.assertTrue(import_instance.image_files.filter(id=onboarding_image.id).exists())

        # Check that file exists on disk
        self.assertTrue(os.path.exists(onboarding_image.image.path))

        # Check file path structure
        self.assertIn(f"onboarding/user_{self.user.id}/import_{import_instance.id}/raw/", onboarding_image.image.name)

    def test_upload_path_correctness(self):
        """Test that upload paths are generated correctly."""
        import_instance = OnboardingImport.objects.create(user=self.user)

        image_content = b"fake image content"
        image_file = ContentFile(image_content, name="menu.jpg")

        onboarding_image = OnboardingImage.objects.create(
            import_instance=import_instance,
            image=image_file
        )

        # Check path contains expected structure
        path = onboarding_image.image.name
        self.assertIn("onboarding/", path)
        self.assertIn(f"/user_{self.user.id}/", path)
        self.assertIn(f"/import_{import_instance.id}/", path)
        self.assertIn("/raw/", path)
        self.assertTrue(path.endswith("menu.jpg"))

    @patch('onboarding.services.ai_onboarding.OpenAIService.generate_with_images')
    def test_ai_service_uses_stored_file_paths(self, mock_generate_images):
        """Test that AI service uses actual stored file paths, not raw uploaded files."""
        mock_generate_images.return_value = json.dumps({
            "menu": [{"category": "Test", "items": []}],
            "branding": {}
        })

        import_instance = OnboardingImport.objects.create(user=self.user)

        # Create test image
        image_content = b"fake image content"
        image_file = ContentFile(image_content, name="test.jpg")
        onboarding_image = OnboardingImage.objects.create(
            import_instance=import_instance,
            image=image_file
        )

        # Process the import
        result = self.service.process_import(import_instance.id)

        # Verify that generate_with_images was called with file paths
        mock_generate_images.assert_called_once()
        call_args = mock_generate_images.call_args
        image_inputs = call_args[1]['image_inputs']  # kwargs

        # Should have one image input
        self.assertEqual(len(image_inputs), 1)

        # The image input should be using base64 encoded data
        image_input = image_inputs[0]
        self.assertEqual(image_input['type'], 'image_url')
        self.assertIn('image_url', image_input)
        self.assertTrue(image_input['image_url']['url'].startswith('data:image/'))

    def test_cleanup_files_removes_files_and_relationships(self):
        """Test that cleanup_files method removes associated files and clears relationships."""
        import_instance = OnboardingImport.objects.create(user=self.user)

        # Create test images
        image_content = b"fake image content"
        image_file1 = ContentFile(image_content, name="test1.jpg")
        image_file2 = ContentFile(image_content, name="test2.jpg")

        onboarding_image1 = OnboardingImage.objects.create(
            import_instance=import_instance,
            image=image_file1
        )
        onboarding_image2 = OnboardingImage.objects.create(
            import_instance=import_instance,
            image=image_file2
        )

        # Verify files exist
        self.assertTrue(os.path.exists(onboarding_image1.image.path))
        self.assertTrue(os.path.exists(onboarding_image2.image.path))
        self.assertEqual(import_instance.image_files.count(), 2)

        # Cleanup files
        import_instance.cleanup_files()

        # Verify files are removed and relationships cleared
        self.assertEqual(import_instance.images.count(), 0)
        self.assertFalse(os.path.exists(onboarding_image1.image.path))
        self.assertFalse(os.path.exists(onboarding_image2.image.path))


class OnboardingSerializerTests(TestCase):
    """Test serializer functionality."""

    def setUp(self):
        self.user = UserFactory()
        self.service = AIOnboardingService()

    def test_onboarding_import_serializer_handles_images(self):
        """Test that OnboardingImportSerializer properly serializes images."""
        import_instance = OnboardingImport.objects.create(user=self.user, raw_text="Test")

        # Create test images
        image_content = b"fake image content"
        image_file1 = ContentFile(image_content, name="test1.jpg")
        image_file2 = ContentFile(image_content, name="test2.jpg")

        onboarding_image1 = OnboardingImage.objects.create(
            import_instance=import_instance,
            image=image_file1
        )
        onboarding_image2 = OnboardingImage.objects.create(
            import_instance=import_instance,
            image=image_file2
        )

        # Serialize the instance
        from onboarding.api.serializers import OnboardingImportSerializer
        serializer = OnboardingImportSerializer(import_instance)
        data = serializer.data

        # Check that images are properly serialized
        self.assertIn('images', data)
        self.assertEqual(len(data['images']), 2)

        # Check image data structure
        image_data = data['images'][0]
        self.assertIn('id', image_data)
        self.assertIn('url', image_data)
        self.assertIn('created_at', image_data)

        # Check that URL is properly generated
        self.assertTrue(image_data['url'].startswith('/media/'))
        self.assertIn(f"/onboarding/user_{self.user.id}/import_{import_instance.id}/raw/", image_data['url'])
