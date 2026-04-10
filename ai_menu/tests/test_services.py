from decimal import Decimal
from django.test import TestCase
from menu.tests.factories import ItemFactory, CategoryFactory
from ai_menu.services.menu_analyzer import MenuAnalyzerService


class MenuAnalyzerServiceTests(TestCase):
    """Test cases for MenuAnalyzerService."""

    def setUp(self):
        """Set up test fixtures."""
        self.category = CategoryFactory()

    def test_analyze_burger_item(self):
        """Test analyzing a burger item."""
        burger = ItemFactory(
            category=self.category,
            name='Classic Burger',
            description='Beef patty with fresh vegetables',
            base_price=Decimal('8.99'),
        )
        result = MenuAnalyzerService.analyze_item(burger)

        self.assertEqual(result['detected_category'], 'burger')
        self.assertTrue(len(result['free_options_suggestions']) > 0)
        self.assertTrue(len(result['paid_options_suggestions']) > 0)
        self.assertTrue(len(result['bundles_suggestions']) > 0)

        # Check specific burger suggestions
        self.assertIn('Extra lettuce', result['free_options_suggestions'])
        self.assertIn('Add bacon (+€1.50)', result['paid_options_suggestions'])
        self.assertIn('Burger + Fries combo', result['bundles_suggestions'])

    def test_analyze_bowl_item(self):
        """Test analyzing a bowl item."""
        bowl = ItemFactory(
            category=self.category,
            name='Poke Bowl',
            description='Fresh fish bowl with rice',
            base_price=Decimal('12.99'),
        )
        result = MenuAnalyzerService.analyze_item(bowl)

        self.assertEqual(result['detected_category'], 'bowl')
        self.assertIn('Extra vegetables', result['free_options_suggestions'])
        self.assertIn('Add extra protein (+€2.00)', result['paid_options_suggestions'])
        self.assertIn('Bowl + Drink combo', result['bundles_suggestions'])

    def test_analyze_taco_item(self):
        """Test analyzing a taco item."""
        taco = ItemFactory(
            category=self.category,
            name='Tacos al Pastor',
            description='Delicious tacos with pineapple',
            base_price=Decimal('7.99'),
        )
        result = MenuAnalyzerService.analyze_item(taco)

        self.assertEqual(result['detected_category'], 'taco')
        self.assertIn('Extra onions', result['free_options_suggestions'])
        self.assertIn('Add spicy sauce (+€0.50)', result['paid_options_suggestions'])
        self.assertIn('Tacos (3) + Drink combo', result['bundles_suggestions'])

    def test_analyze_generic_item(self):
        """Test analyzing an item with no specific category."""
        generic = ItemFactory(
            category=self.category,
            name='Side Salad',
            description='Fresh garden salad',
            base_price=Decimal('3.99'),
        )
        result = MenuAnalyzerService.analyze_item(generic)

        self.assertEqual(result['detected_category'], 'other')
        self.assertEqual(result['free_options_suggestions'], [])
        self.assertEqual(result['paid_options_suggestions'], [])
        self.assertEqual(result['bundles_suggestions'], [])

    def test_analyze_item_case_insensitive(self):
        """Test that analysis is case-insensitive."""
        burger1 = ItemFactory(
            category=self.category,
            name='BURGER',
            description='Beef patty',
            base_price=Decimal('8.99'),
        )
        burger2 = ItemFactory(
            category=self.category,
            name='Burger',
            description='beef patty',
            base_price=Decimal('8.99'),
        )
        result1 = MenuAnalyzerService.analyze_item(burger1)
        result2 = MenuAnalyzerService.analyze_item(burger2)

        self.assertEqual(result1['detected_category'], result2['detected_category'])

    def test_analyze_item_with_empty_description(self):
        """Test analyzing item with empty description."""
        item = ItemFactory(
            category=self.category,
            name='Burger',
            description='',
            base_price=Decimal('8.99'),
        )
        result = MenuAnalyzerService.analyze_item(item)

        self.assertEqual(result['detected_category'], 'burger')

    def test_result_structure(self):
        """Test that result has expected structure."""
        item = ItemFactory(category=self.category, name='Burger')
        result = MenuAnalyzerService.analyze_item(item)

        self.assertIn('detected_category', result)
        self.assertIn('free_options_suggestions', result)
        self.assertIn('paid_options_suggestions', result)
        self.assertIn('bundles_suggestions', result)

        self.assertIsInstance(result['detected_category'], str)
        self.assertIsInstance(result['free_options_suggestions'], list)
        self.assertIsInstance(result['paid_options_suggestions'], list)
        self.assertIsInstance(result['bundles_suggestions'], list)
