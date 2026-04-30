"""
Tests for AIRecommendationGeneratorService.

Tests cover:
- Success case with valid OpenAI response
- Fallback when OpenAI returns invalid JSON
- Fallback when OpenAI API raises exception
- Response validation
- Database persistence
- Error handling
"""
import json
from decimal import Decimal
from unittest.mock import patch, MagicMock

from django.test import TestCase
from django.core.exceptions import ValidationError

from menu.tests.factories import ItemFactory, CategoryFactory, FoodTruckFactory, MenuFactory
from menu.models import Option, OptionGroup
from ai_menu.models import AIRecommendation
from ai_menu.services.recommendation_generator import AIRecommendationGeneratorService


class AIRecommendationGeneratorServiceTests(TestCase):
    """Tests for AIRecommendationGeneratorService."""

    def setUp(self):
        """Set up test fixtures."""
        self.foodtruck = FoodTruckFactory(name='Test Truck', default_language='fr')
        self.menu = MenuFactory(food_truck=self.foodtruck, name='Main Menu')
        self.category = CategoryFactory(menu=self.menu, name='Burgers')
        self.item = ItemFactory(
            category=self.category,
            name='Classic Burger',
            description='Beef patty with fresh vegetables',
            base_price=Decimal('8.99'),
        )
        self.service = AIRecommendationGeneratorService()

    def test_prepare_item_context(self):
        """Test that item context is properly prepared."""
        context = self.service._prepare_item_context(self.item)

        self.assertEqual(context['item_name'], 'Classic Burger')
        self.assertEqual(context['item_description'], 'Beef patty with fresh vegetables')
        self.assertEqual(context['item_base_price'], 8.99)
        self.assertEqual(context['category_name'], 'Burgers')
        self.assertEqual(context['menu_name'], 'Main Menu')
        self.assertEqual(context['foodtruck_name'], 'Test Truck')
        self.assertEqual(context['foodtruck_language'], 'fr')

    def test_prepare_item_context_with_missing_description(self):
        """Test context preparation with missing item description."""
        item = ItemFactory(
            category=self.category,
            name='Simple Item',
            description='',
            base_price=Decimal('5.00'),
        )
        context = self.service._prepare_item_context(item)

        self.assertEqual(context['item_name'], 'Simple Item')
        self.assertEqual(context['item_description'], '')
        self.assertEqual(context['item_base_price'], 5.0)

    def test_extract_price_from_string(self):
        """Test price extraction from formatted strings."""
        price1 = self.service._extract_price_from_string('+€1.50')
        price2 = self.service._extract_price_from_string('€2.00')
        price3 = self.service._extract_price_from_string('Add bacon (+€1.50)')
        price4 = self.service._extract_price_from_string('€0.50')

        self.assertEqual(price1, 1.50)
        self.assertEqual(price2, 2.0)
        self.assertEqual(price3, 1.50)
        self.assertEqual(price4, 0.50)

    @patch('ai_menu.services.recommendation_generator.OpenAIService')
    def test_generate_and_store_success(self, mock_openai_class):
        """Test successful generation and storage of recommendations."""
        # Mock OpenAI response
        openai_response = json.dumps({
            "detected_category": "burger",
            "free_options": [
                {"name": "Extra lettuce", "reason": "Adds freshness"},
                {"name": "Extra sauce", "reason": "Enhances flavor"}
            ],
            "paid_options": [
                {"name": "Add bacon", "suggested_price": 1.50, "reason": "Premium upgrade"}
            ],
            "bundles": [
                {"name": "Burger + Fries combo", "items": ["Burger", "Fries"], "reason": "Increases AOV"}
            ]
        })

        mock_openai = MagicMock()
        mock_openai.generate.return_value = openai_response
        mock_openai_class.return_value = mock_openai

        # Create service with mocked OpenAI
        service = AIRecommendationGeneratorService()
        service.openai_service = mock_openai

        # Call generate
        result = service.generate_and_store_for_item(self.item)

        # Verify result
        self.assertEqual(result['status'], 'success')
        self.assertEqual(len(result['recommendations']), 4)  # 2 free + 1 paid + 1 bundle

        # Verify recommendations were created
        recommendations = AIRecommendation.objects.for_item(self.item)
        self.assertEqual(recommendations.count(), 4)
        self.assertTrue(all(rec.language_code == 'fr' for rec in recommendations))

        # Verify types
        free_opts = recommendations.filter(recommendation_type='free_option')
        paid_opts = recommendations.filter(recommendation_type='paid_option')
        bundles = recommendations.filter(recommendation_type='bundle')

        self.assertEqual(free_opts.count(), 2)
        self.assertEqual(paid_opts.count(), 1)
        self.assertEqual(bundles.count(), 1)

        # Verify payloads - check that expected values exist (order may vary)
        free_names = [r.payload['name'] for r in free_opts]
        self.assertIn('Extra lettuce', free_names)
        self.assertIn('Extra sauce', free_names)

        paid_rec = paid_opts.first()
        self.assertEqual(paid_rec.payload['name'], 'Add bacon')
        self.assertEqual(paid_rec.payload['suggested_price'], 1.50)
        self.assertIn('Premium', paid_rec.payload['reason'])

        bundle_rec = bundles.first()
        self.assertIn('Burger', bundle_rec.payload['name'])
        self.assertIn('Fries', bundle_rec.payload['name'])
        self.assertTrue(len(bundle_rec.payload['items']) > 0)

    @patch('ai_menu.services.recommendation_generator.OpenAIService')
    def test_generate_with_fallback_invalid_json(self, mock_openai_class):
        """Test fallback when OpenAI returns invalid JSON."""
        mock_openai = MagicMock()
        mock_openai.generate.return_value = "This is not JSON"
        mock_openai_class.return_value = mock_openai

        service = AIRecommendationGeneratorService()
        service.openai_service = mock_openai

        result = service.generate_and_store_for_item(self.item)

        # Should fall back to MenuAnalyzerService
        self.assertEqual(result['status'], 'fallback')
        self.assertIn('fallback_reason', result)
        self.assertTrue(len(result['recommendations']) > 0)

        recommendation = AIRecommendation.objects.for_item(self.item).first()
        self.assertEqual(recommendation.language_code, 'fr')
        self.assertEqual(recommendation.payload['reason'], 'Suggestion basee sur des regles')

    def test_build_ai_prompt_uses_foodtruck_language(self):
        """Prompt should request localized output based on the food truck language."""
        context = self.service._prepare_item_context(self.item)
        prompt = self.service._build_ai_prompt(self.item, context)

        self.assertIn('French', prompt)
        self.assertIn('must be written in French', prompt)

    def test_prepare_item_context_includes_category_options(self):
        """Context should expose existing category options and assignment state."""
        group = OptionGroup.objects.create(
            category=self.category,
            name='Sauces',
            required=False,
            min_choices=0,
        )
        option = Option.objects.create(
            group=group,
            name='Sauce maison',
            price_modifier=Decimal('0.00'),
            is_available=True,
        )
        option.items.add(self.item)

        context = self.service._prepare_item_context(self.item)

        self.assertIn('category_options', context)
        self.assertTrue(any(row['id'] == option.id for row in context['category_options']))

    @patch('ai_menu.services.recommendation_generator.OpenAIService')
    def test_generate_persists_existing_option_reviews(self, mock_openai_class):
        """OpenAI option review payload should be persisted as actionable recommendations."""
        group = OptionGroup.objects.create(
            category=self.category,
            name='Add-ons',
            required=False,
            min_choices=0,
        )
        option = Option.objects.create(
            group=group,
            name='Truffle mayo',
            price_modifier=Decimal('1.50'),
            is_available=True,
        )

        openai_response = json.dumps({
            "detected_category": "burger",
            "free_options": [],
            "paid_options": [],
            "bundles": [],
            "option_reviews": [
                {
                    "existing_option_id": option.id,
                    "name": option.name,
                    "suggested_action": "enable",
                    "reason": "Fits the premium profile",
                    "current_status": "disabled",
                    "option_type": "paid_option"
                }
            ]
        })

        mock_openai = MagicMock()
        mock_openai.generate.return_value = openai_response
        mock_openai_class.return_value = mock_openai

        service = AIRecommendationGeneratorService()
        service.openai_service = mock_openai

        result = service.generate_and_store_for_item(self.item)

        self.assertEqual(result['status'], 'success')
        rec = AIRecommendation.objects.for_item(self.item).get(recommendation_type='paid_option')
        self.assertEqual(rec.payload.get('existing_option_id'), option.id)
        self.assertEqual(rec.payload.get('suggested_action'), 'enable')

    @patch('ai_menu.services.recommendation_generator.OpenAIService')
    def test_generate_converts_duplicate_suggestion_to_existing_option_review(self, mock_openai_class):
        """AI new-option suggestions matching existing category options must not create duplicate candidates."""
        group = OptionGroup.objects.create(
            category=self.category,
            name='Sauces',
            required=False,
            min_choices=0,
        )
        option = Option.objects.create(
            group=group,
            name='Sauce maison',
            price_modifier=Decimal('0.00'),
            is_available=True,
        )

        openai_response = json.dumps({
            "detected_category": "burger",
            "free_options": [
                {"name": "Sauce maison", "reason": "Popular pairing"}
            ],
            "paid_options": [],
            "bundles": [],
            "option_reviews": []
        })

        mock_openai = MagicMock()
        mock_openai.generate.return_value = openai_response
        mock_openai_class.return_value = mock_openai

        service = AIRecommendationGeneratorService()
        service.openai_service = mock_openai

        result = service.generate_and_store_for_item(self.item)

        self.assertEqual(result['status'], 'success')
        rec = AIRecommendation.objects.for_item(self.item).get(recommendation_type='free_option')
        self.assertEqual(rec.payload.get('existing_option_id'), option.id)
        self.assertEqual(rec.payload.get('suggested_action'), 'enable')

    @patch('ai_menu.services.recommendation_generator.OpenAIService')
    def test_generate_ensures_review_for_all_enabled_item_options(self, mock_openai_class):
        """Enabled item options must receive an opinion even when option_reviews is missing."""
        group = OptionGroup.objects.create(
            category=self.category,
            name='Supplements',
            required=False,
            min_choices=0,
        )
        option = Option.objects.create(
            group=group,
            name='Sauce maison',
            price_modifier=Decimal('0.00'),
            is_available=True,
        )
        option.items.add(self.item)

        openai_response = json.dumps({
            "detected_category": "burger",
            "free_options": [],
            "paid_options": [],
            "bundles": []
        })

        mock_openai = MagicMock()
        mock_openai.generate.return_value = openai_response
        mock_openai_class.return_value = mock_openai

        service = AIRecommendationGeneratorService()
        service.openai_service = mock_openai

        service.generate_and_store_for_item(self.item)

        review = AIRecommendation.objects.for_item(self.item).get(payload__existing_option_id=option.id)
        self.assertEqual(review.payload.get('suggested_action'), 'keep')
        self.assertEqual(review.payload.get('current_status'), 'enabled')

    @patch('ai_menu.services.recommendation_generator.OpenAIService')
    def test_generate_with_fallback_api_error(self, mock_openai_class):
        """Test fallback when OpenAI API raises exception."""
        mock_openai = MagicMock()
        mock_openai.generate.side_effect = Exception("API Error")
        mock_openai_class.return_value = mock_openai

        service = AIRecommendationGeneratorService()
        service.openai_service = mock_openai

        result = service.generate_and_store_for_item(self.item)

        # Should fall back to MenuAnalyzerService
        self.assertEqual(result['status'], 'fallback')
        self.assertIn('fallback_reason', result)

    @patch('ai_menu.services.recommendation_generator.OpenAIService')
    def test_generate_clears_pending_before_creating(self, mock_openai_class):
        """Test that old pending recommendations are cleared before creating new ones."""
        # Create some existing pending recommendations
        AIRecommendation.objects.create(
            item=self.item,
            recommendation_type='free_option',
            payload={'name': 'Old suggestion'},
            status='pending'
        )

        openai_response = json.dumps({
            "detected_category": "burger",
            "free_options": [
                {"name": "New suggestion", "reason": "Better one"}
            ],
            "paid_options": [],
            "bundles": []
        })

        mock_openai = MagicMock()
        mock_openai.generate.return_value = openai_response
        mock_openai_class.return_value = mock_openai

        service = AIRecommendationGeneratorService()
        service.openai_service = mock_openai

        # Generate new recommendations
        result = service.generate_and_store_for_item(self.item)

        # Should only have 1 recommendation (old one cleared)
        recommendations = AIRecommendation.objects.for_item(self.item).pending()
        self.assertEqual(recommendations.count(), 1)
        self.assertEqual(recommendations.first().payload['name'], 'New suggestion')

    @patch('ai_menu.services.recommendation_generator.OpenAIService')
    def test_generate_preserves_accepted_rejected(self, mock_openai_class):
        """Test that accepted/rejected recommendations are not cleared."""
        # Create accepted and rejected recommendations
        AIRecommendation.objects.create(
            item=self.item,
            recommendation_type='free_option',
            payload={'name': 'Accepted suggestion'},
            status='accepted'
        )
        AIRecommendation.objects.create(
            item=self.item,
            recommendation_type='free_option',
            payload={'name': 'Rejected suggestion'},
            status='rejected'
        )

        openai_response = json.dumps({
            "detected_category": "burger",
            "free_options": [
                {"name": "New suggestion", "reason": "New one"}
            ],
            "paid_options": [],
            "bundles": []
        })

        mock_openai = MagicMock()
        mock_openai.generate.return_value = openai_response
        mock_openai_class.return_value = mock_openai

        service = AIRecommendationGeneratorService()
        service.openai_service = mock_openai

        # Generate
        service.generate_and_store_for_item(self.item)

        # Should have: 1 accepted + 1 rejected + 1 new pending = 3 total
        all_recs = AIRecommendation.objects.for_item(self.item)
        self.assertEqual(all_recs.count(), 3)
        self.assertEqual(all_recs.filter(status='accepted').count(), 1)
        self.assertEqual(all_recs.filter(status='rejected').count(), 1)
        self.assertEqual(all_recs.filter(status='pending').count(), 1)

    def test_validate_recommendations_data_invalid_structure(self):
        """Test validation rejects invalid data structures."""
        # Missing required keys
        invalid_data = {
            'detected_category': 'burger',
            # Missing: free_options, paid_options, bundles
        }
        self.assertFalse(self.service._validate_recommendations_data(invalid_data))

        # Empty dict
        self.assertFalse(self.service._validate_recommendations_data({}))

        # None
        self.assertFalse(self.service._validate_recommendations_data(None))

    def test_validate_recommendations_data_invalid_types(self):
        """Test validation rejects invalid data types."""
        valid_base = {
            'detected_category': 'burger',
            'free_options': [],
            'paid_options': [],
            'bundles': [],
        }

        # detected_category not a string
        invalid = {**valid_base, 'detected_category': 123}
        self.assertFalse(self.service._validate_recommendations_data(invalid))

        # free_options not a list
        invalid = {**valid_base, 'free_options': 'not a list'}
        self.assertFalse(self.service._validate_recommendations_data(invalid))

    def test_validate_recommendations_data_invalid_items(self):
        """Test validation of item structures."""
        # Missing 'name' in free_option
        invalid = {
            'detected_category': 'burger',
            'free_options': [{'reason': 'Missing name'}],
            'paid_options': [],
            'bundles': [],
        }
        self.assertFalse(self.service._validate_recommendations_data(invalid))

        # Missing 'suggested_price' in paid_option
        invalid = {
            'detected_category': 'burger',
            'free_options': [],
            'paid_options': [{'name': 'Add bacon', 'reason': 'Missing price'}],
            'bundles': [],
        }
        self.assertFalse(self.service._validate_recommendations_data(invalid))

    def test_validate_recommendations_data_valid(self):
        """Test validation accepts valid data."""
        valid = {
            'detected_category': 'burger',
            'free_options': [
                {'name': 'Extra lettuce', 'reason': 'Adds freshness'}
            ],
            'paid_options': [
                {'name': 'Add bacon', 'suggested_price': 1.5, 'reason': 'Premium'}
            ],
            'bundles': [
                {'name': 'Combo', 'items': ['Burger'], 'reason': 'Increase AOV'}
            ],
        }
        self.assertTrue(self.service._validate_recommendations_data(valid))

    def test_parse_openai_response_with_markdown(self):
        """Test parsing response wrapped in markdown code blocks."""
        response_with_markdown = """```json
{
  "detected_category": "burger",
  "free_options": [],
  "paid_options": [],
  "bundles": []
}
```"""
        result = self.service._parse_openai_response(response_with_markdown)
        self.assertIsNotNone(result)
        self.assertEqual(result['detected_category'], 'burger')

    def test_parse_openai_response_without_markdown(self):
        """Test parsing plainJSON response."""
        response_plain = """{
  "detected_category": "burger",
  "free_options": [],
  "paid_options": [],
  "bundles": []
}"""
        result = self.service._parse_openai_response(response_plain)
        self.assertIsNotNone(result)
        self.assertEqual(result['detected_category'], 'burger')

    def test_parse_openai_response_invalid_json(self):
        """Test parsing invalid JSON returns None."""
        invalid_response = "This is not JSON"
        result = self.service._parse_openai_response(invalid_response)
        self.assertIsNone(result)

    def test_parse_openai_response_empty(self):
        """Test parsing empty response returns None."""
        result = self.service._parse_openai_response("")
        self.assertIsNone(result)

    def test_generate_and_store_invalid_item(self):
        """Test generate_and_store raises ValidationError for invalid item."""
        with self.assertRaises(ValidationError):
            self.service.generate_and_store_for_item(None)

        # Create unsaved item (without PKor save to DB)
        unsaved_item = ItemFactory(
            category=self.category,
            name='Unsaved Item',
            description='Test',
            base_price=Decimal('5.00'),
        )
        # Delete to make it unsaved
        item_id = unsaved_item.id
        unsaved_item.delete()

        # Create a new instance without PK
        from menu.models import Item
        unsaved_instance = Item(
            category=self.category,
            name='Never saved',
            description='Test',
            base_price=Decimal('5.00'),
        )

        with self.assertRaises(ValidationError):
            self.service.generate_and_store_for_item(unsaved_instance)

    @patch('ai_menu.services.recommendation_generator.OpenAIService')
    def test_generate_and_store_handles_database_error(self, mock_openai_class):
        """Test generate_and_store handles database errors gracefully."""
        openai_response = json.dumps({
            "detected_category": "burger",
            "free_options": [{"name": "Test", "reason": "Test"}],
            "paid_options": [],
            "bundles": []
        })

        mock_openai = MagicMock()
        mock_openai.generate.return_value = openai_response
        mock_openai_class.return_value = mock_openai

        service = AIRecommendationGeneratorService()
        service.openai_service = mock_openai

        # Mock AIRecommendation.objects.create to raise error
        with patch('ai_menu.services.recommendation_generator.AIRecommendation.objects.create',
                   side_effect=Exception("Database error")):
            result = service.generate_and_store_for_item(self.item)

        self.assertEqual(result['status'], 'error')
        self.assertIn('error', result)

    def test_clear_pending_recommendations(self):
        """Test that only pending recommendations are cleared."""
        # Create mixed status recommendations
        pending = AIRecommendation.objects.create(
            item=self.item,
            recommendation_type='free_option',
            payload={},
            status='pending'
        )
        accepted = AIRecommendation.objects.create(
            item=self.item,
            recommendation_type='free_option',
            payload={},
            status='accepted'
        )

        # Clear pending
        self.service._clear_pending_recommendations(self.item)

        # Pending should be gone, accepted should remain
        self.assertFalse(AIRecommendation.objects.filter(id=pending.id).exists())
        self.assertTrue(AIRecommendation.objects.filter(id=accepted.id).exists())

    def test_persist_recommendations_structure(self):
        """Test that recommendations are persisted with correct structure."""
        recommendations_data = {
            'detected_category': 'burger',
            'free_options': [
                {'name': 'Extra lettuce', 'reason': 'Adds freshness'}
            ],
            'paid_options': [
                {'name': 'Add bacon', 'suggested_price': 1.5, 'reason': 'Premium'}
            ],
            'bundles': [
                {'name': 'Burger + Fries', 'items': ['Burger', 'Fries'], 'reason': 'AOV increase'}
            ]
        }

        created_ids = self.service._persist_recommendations(self.item, recommendations_data)

        # Verify all were created
        self.assertEqual(len(created_ids), 3)

        # Verify types and payloads
        free_rec = AIRecommendation.objects.get(id=created_ids[0])
        self.assertEqual(free_rec.recommendation_type, 'free_option')
        self.assertEqual(free_rec.payload['name'], 'Extra lettuce')

        paid_rec = AIRecommendation.objects.get(id=created_ids[1])
        self.assertEqual(paid_rec.recommendation_type, 'paid_option')
        self.assertEqual(paid_rec.payload['suggested_price'], 1.5)

        bundle_rec = AIRecommendation.objects.get(id=created_ids[2])
        self.assertEqual(bundle_rec.recommendation_type, 'bundle')
        self.assertEqual(bundle_rec.payload['name'], 'Burger + Fries')
