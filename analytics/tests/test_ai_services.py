from datetime import timedelta
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone

from analytics.models import Event, EventOpportunity, RevenuePrediction
from analytics.services.event_ai_service import EventAIService
from analytics.services.location_ai_service import LocationAIService
from analytics.services.revenue_prediction_service import RevenuePredictionService
from foodtrucks.models import LocationScore
from foodtrucks.tests.factories import CategoryFactory, FoodTruckFactory, ItemFactory, MenuFactory, UserFactory
from menu.services.pricing_ai_service import PricingAIService
from menu.models import PricingSuggestion
from orders.tests.factories import OrderFactory, PickupSlotFactory


class AIServicesTests(TestCase):
    def setUp(self):
        self.owner = UserFactory()
        self.foodtruck = FoodTruckFactory(owner=self.owner)
        self.menu = MenuFactory(food_truck=self.foodtruck)
        self.category = CategoryFactory(menu=self.menu, name='Burgers')
        self.item = ItemFactory(category=self.category, name='Classic Burger', base_price=Decimal('10.00'))

    def _create_paid_order(self, amount='20.00', paid_at=None):
        slot_start = timezone.now() + timedelta(hours=2)
        slot = PickupSlotFactory(
            food_truck=self.foodtruck,
            start_time=slot_start,
            end_time=slot_start + timedelta(hours=1),
            capacity=10,
        )
        order = OrderFactory(
            user=self.owner,
            food_truck=self.foodtruck,
            pickup_slot=slot,
            status='completed',
        )
        order.total_amount = Decimal(amount)
        order.total_price = Decimal(amount)
        order.paid_at = paid_at or timezone.now()
        order.save(update_fields=['status', 'total_amount', 'total_price', 'paid_at'])
        return order

    def test_location_score_computation(self):
        self._create_paid_order(amount='22.00', paid_at=timezone.now() - timedelta(days=1))
        service = LocationAIService(self.foodtruck)

        result = service.compute_score(float(self.foodtruck.latitude), float(self.foodtruck.longitude))

        self.assertIn('score', result)
        self.assertIn('breakdown', result)
        self.assertGreaterEqual(result['score'], 0)
        self.assertLessEqual(result['score'], 100)
        self.assertTrue(LocationScore.objects.filter(foodtruck=self.foodtruck).exists())

    def test_pricing_suggestion_valid(self):
        for _ in range(4):
            self._create_paid_order(amount='18.00', paid_at=timezone.now() - timedelta(days=2))

        service = PricingAIService()
        result = service.suggest_price(self.item)

        self.assertIn('suggested_price', result)
        self.assertIn('reason', result)
        self.assertGreater(result['suggested_price'], Decimal('0.00'))
        self.assertTrue(PricingSuggestion.objects.filter(item=self.item).exists())

    def test_event_opportunity_scoring(self):
        self._create_paid_order(amount='25.00', paid_at=timezone.now() - timedelta(days=3))
        event = Event.objects.create(
            name='City Street Food Festival',
            latitude=self.foodtruck.latitude,
            longitude=self.foodtruck.longitude,
            start_date=timezone.localdate() + timedelta(days=1),
            end_date=timezone.localdate() + timedelta(days=2),
            expected_attendance=3000,
        )

        service = EventAIService()
        result = service.evaluate_event(self.foodtruck, event)

        self.assertIn('opportunity_score', result)
        self.assertIn('predicted_revenue', result)
        self.assertGreaterEqual(result['opportunity_score'], 0)
        self.assertLessEqual(result['opportunity_score'], 100)
        self.assertGreater(result['predicted_revenue'], Decimal('50.00'))
        self.assertTrue(
            EventOpportunity.objects.filter(foodtruck=self.foodtruck, event=event).exists()
        )

    def test_revenue_prediction_fallback(self):
        # No paid order on purpose to force deterministic fallback.
        service = RevenuePredictionService()
        target_date = timezone.localdate() + timedelta(days=1)

        result = service.predict_day(self.foodtruck, target_date)

        self.assertEqual(result['breakdown']['method'], 'fallback_simple_average')
        self.assertGreater(result['predicted_revenue'], Decimal('0.00'))
        self.assertTrue(
            RevenuePrediction.objects.filter(foodtruck=self.foodtruck, date=target_date).exists()
        )
