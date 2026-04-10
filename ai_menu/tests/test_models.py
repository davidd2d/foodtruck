from decimal import Decimal
from django.test import TestCase
from django.core.exceptions import ValidationError
from menu.tests.factories import ItemFactory, CategoryFactory, MenuFactory
from foodtrucks.tests.factories import FoodTruckFactory
from ai_menu.models import AIRecommendation


class AIRecommendationModelTests(TestCase):
    """Test cases for the AIRecommendation model."""

    def setUp(self):
        """Set up test fixtures."""
        self.foodtruck = FoodTruckFactory()
        self.menu = MenuFactory(food_truck=self.foodtruck)
        self.category = CategoryFactory(menu=self.menu)
        self.item = ItemFactory(category=self.category, name='Classic Burger')

    def test_create_recommendation(self):
        """Test creating a recommendation."""
        rec = AIRecommendation.objects.create(
            item=self.item,
            recommendation_type='free_option',
            payload={'suggestion': 'Extra lettuce'},
            status='pending',
        )
        self.assertEqual(rec.item, self.item)
        self.assertEqual(rec.recommendation_type, 'free_option')
        self.assertTrue(rec.is_pending())

    def test_is_pending(self):
        """Test is_pending method."""
        rec = AIRecommendation.objects.create(
            item=self.item,
            recommendation_type='paid_option',
            payload={'suggestion': 'Add cheese'},
            status='pending',
        )
        self.assertTrue(rec.is_pending())

        rec.status = 'accepted'
        self.assertFalse(rec.is_pending())

    def test_accept_recommendation(self):
        """Test accepting a pending recommendation."""
        rec = AIRecommendation.objects.create(
            item=self.item,
            recommendation_type='free_option',
            payload={'suggestion': 'Grilled onions'},
            status='pending',
        )
        rec.accept()
        rec.refresh_from_db()
        self.assertEqual(rec.status, 'accepted')

    def test_accept_non_pending_fails(self):
        """Test accepting non-pending recommendation raises error."""
        rec = AIRecommendation.objects.create(
            item=self.item,
            recommendation_type='free_option',
            payload={'suggestion': 'Pickles'},
            status='accepted',
        )
        with self.assertRaises(ValidationError):
            rec.accept()

    def test_reject_recommendation(self):
        """Test rejecting a pending recommendation."""
        rec = AIRecommendation.objects.create(
            item=self.item,
            recommendation_type='bundle',
            payload={'suggestion': 'Burger + Fries combo'},
            status='pending',
        )
        rec.reject()
        rec.refresh_from_db()
        self.assertEqual(rec.status, 'rejected')

    def test_reject_non_pending_fails(self):
        """Test rejecting non-pending recommendation raises error."""
        rec = AIRecommendation.objects.create(
            item=self.item,
            recommendation_type='bundle',
            payload={'suggestion': 'Burger + Fries combo'},
            status='rejected',
        )
        with self.assertRaises(ValidationError):
            rec.reject()

    def test_string_representation(self):
        """Test string representation of recommendation."""
        rec = AIRecommendation.objects.create(
            item=self.item,
            recommendation_type='free_option',
            payload={'suggestion': 'Extra lettuce'},
            status='pending',
        )
        self.assertIn(self.item.name, str(rec))
        self.assertIn('Free Option', str(rec))
        self.assertIn('Pending', str(rec))


class AIRecommendationQuerySetTests(TestCase):
    """Test cases for CustomQuerySet and Manager methods."""

    def setUp(self):
        """Set up test fixtures."""
        self.foodtruck = FoodTruckFactory()
        self.menu = MenuFactory(food_truck=self.foodtruck)
        self.category = CategoryFactory(menu=self.menu)
        self.item1 = ItemFactory(category=self.category, name='Burger')
        self.item2 = ItemFactory(category=self.category, name='Bowl')

        # Create recommendations with different statuses
        self.pending_rec = AIRecommendation.objects.create(
            item=self.item1,
            recommendation_type='free_option',
            payload={'suggestion': 'Lettuce'},
            status='pending',
        )
        self.accepted_rec = AIRecommendation.objects.create(
            item=self.item1,
            recommendation_type='paid_option',
            payload={'suggestion': 'Cheese'},
            status='accepted',
        )
        self.rejected_rec = AIRecommendation.objects.create(
            item=self.item2,
            recommendation_type='bundle',
            payload={'suggestion': 'Combo'},
            status='rejected',
        )

    def test_pending_filter(self):
        """Test filtering pending recommendations."""
        pending = AIRecommendation.objects.pending()
        self.assertEqual(pending.count(), 1)
        self.assertEqual(pending.first(), self.pending_rec)

    def test_accepted_filter(self):
        """Test filtering accepted recommendations."""
        accepted = AIRecommendation.objects.accepted()
        self.assertEqual(accepted.count(), 1)
        self.assertEqual(accepted.first(), self.accepted_rec)

    def test_rejected_filter(self):
        """Test filtering rejected recommendations."""
        rejected = AIRecommendation.objects.rejected()
        self.assertEqual(rejected.count(), 1)
        self.assertEqual(rejected.first(), self.rejected_rec)

    def test_for_item_filter(self):
        """Test filtering by item."""
        for_item1 = AIRecommendation.objects.for_item(self.item1)
        self.assertEqual(for_item1.count(), 2)
        self.assertIn(self.pending_rec, for_item1)
        self.assertIn(self.accepted_rec, for_item1)

        for_item2 = AIRecommendation.objects.for_item(self.item2)
        self.assertEqual(for_item2.count(), 1)
        self.assertEqual(for_item2.first(), self.rejected_rec)

    def test_for_foodtruck_filter(self):
        """Test filtering by food truck."""
        other_foodtruck = FoodTruckFactory()
        other_menu = MenuFactory(food_truck=other_foodtruck)
        other_category = CategoryFactory(menu=other_menu)
        other_item = ItemFactory(category=other_category, name='Pizza')
        AIRecommendation.objects.create(
            item=other_item,
            recommendation_type='free_option',
            payload={'suggestion': 'Extra oregano'},
            status='pending',
        )

        foodtruck_recs = AIRecommendation.objects.for_foodtruck(self.foodtruck)
        self.assertEqual(foodtruck_recs.count(), 3)

        other_recs = AIRecommendation.objects.for_foodtruck(other_foodtruck)
        self.assertEqual(other_recs.count(), 1)

    def test_combined_filters(self):
        """Test combining multiple filters."""
        result = AIRecommendation.objects.for_item(self.item1).pending()
        self.assertEqual(result.count(), 1)
        self.assertEqual(result.first(), self.pending_rec)

    def test_ordering_by_created_at_desc(self):
        """Test that recommendations are ordered by created_at desc."""
        all_recs = AIRecommendation.objects.all()
        # Most recent should be first
        self.assertEqual(all_recs.first(), self.rejected_rec)
