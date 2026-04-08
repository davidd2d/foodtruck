from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from foodtrucks.models import Subscription
from foodtrucks.tests.factories import FoodTruckFactory, PlanFactory


class FoodTruckModelTests(TestCase):
    def test_slug_is_auto_generated_from_name(self):
        foodtruck = FoodTruckFactory(name='Barn Burger')

        self.assertEqual(foodtruck.slug, 'barn-burger')

    def test_slug_is_unique_for_duplicate_names(self):
        first = FoodTruckFactory(name='Barn Burger')
        second = FoodTruckFactory(name='Barn Burger')

        self.assertNotEqual(first.slug, second.slug)
        self.assertTrue(second.slug.startswith('barn-burger'))

    def test_get_absolute_url_returns_detail_path(self):
        foodtruck = FoodTruckFactory(name='Barn Burger')

        self.assertEqual(foodtruck.get_absolute_url(), f'/foodtrucks/{foodtruck.slug}/')

    def test_has_active_subscription_checks_plan_and_status(self):
        foodtruck = FoodTruckFactory()

        # Remove default subscription
        foodtruck.subscription.delete()
        self.assertFalse(foodtruck.has_active_subscription())
        self.assertFalse(foodtruck.can_accept_orders())

        # Create inactive subscription
        inactive_plan = PlanFactory(code='pro', allows_ordering=True)
        Subscription.objects.create(food_truck=foodtruck, plan=inactive_plan, status='inactive')
        foodtruck.refresh_from_db()
        self.assertFalse(foodtruck.has_active_subscription())
        self.assertFalse(foodtruck.can_accept_orders())

        # Active pro subscription
        foodtruck.subscription.status = 'active'
        foodtruck.subscription.end_date = timezone.now() + timedelta(days=30)
        foodtruck.subscription.plan = inactive_plan
        foodtruck.subscription.save()
        self.assertTrue(foodtruck.has_active_subscription())
        self.assertTrue(foodtruck.can_accept_orders())

        # Expired subscription
        foodtruck.subscription.end_date = timezone.now() - timedelta(days=1)
        foodtruck.subscription.save()
        self.assertFalse(foodtruck.has_active_subscription())
        self.assertFalse(foodtruck.can_accept_orders())
