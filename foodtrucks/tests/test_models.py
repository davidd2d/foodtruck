from datetime import datetime, time, timedelta

from django.test import TestCase
from django.utils import timezone

from foodtrucks.models import Subscription
from foodtrucks.tests.factories import FoodTruckFactory, PlanFactory
from orders.models import PARIS_TZ, ServiceSchedule, PickupSlot
from orders.tests.factories import OrderFactory, ServiceScheduleFactory, PickupSlotFactory


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


class FoodTruckPickupSlotTests(TestCase):
    def setUp(self):
        self.foodtruck = FoodTruckFactory()
        self.now = timezone.localtime(timezone.now(), PARIS_TZ)

    def test_get_current_service_schedule_returns_active_schedule_for_current_time(self):
        # Create a schedule for today that is currently active
        now = self.now
        schedule = ServiceScheduleFactory(
            food_truck=self.foodtruck,
            day_of_week=now.weekday(),
            start_time=(now - timedelta(hours=1)).time(),
            end_time=(now + timedelta(hours=1)).time(),
            is_active=True
        )

        current_schedule = self.foodtruck.get_current_service_schedule()
        self.assertEqual(current_schedule, schedule)

    def test_get_current_service_schedule_returns_none_when_no_active_schedule(self):
        # No schedules
        current_schedule = self.foodtruck.get_current_service_schedule()
        self.assertIsNone(current_schedule)

    def test_get_next_available_service_schedule_returns_next_schedule(self):
        # Create schedules for different days
        today_schedule = ServiceScheduleFactory(
            food_truck=self.foodtruck,
            day_of_week=self.now.weekday(),
            start_time=time(10, 0),
            end_time=time(12, 0),
            is_active=True
        )
        tomorrow_schedule = ServiceScheduleFactory(
            food_truck=self.foodtruck,
            day_of_week=(self.now.weekday() + 1) % 7,
            start_time=time(10, 0),
            end_time=time(12, 0),
            is_active=True
        )

        next_schedule = self.foodtruck.get_next_available_service_schedule(today_schedule)
        self.assertEqual(next_schedule, tomorrow_schedule)

    def test_get_best_default_pickup_slot_prioritizes_immediate_pickup(self):
        now = self.now
        schedule = ServiceScheduleFactory(
            food_truck=self.foodtruck,
            day_of_week=now.weekday(),
            start_time=(now - timedelta(hours=1)).time(),
            end_time=(now + timedelta(hours=1)).time(),
            is_active=True
        )
        immediate_slot = PickupSlotFactory(
            food_truck=self.foodtruck,
            service_schedule=schedule,
            start_time=now - timedelta(minutes=30),
            end_time=now + timedelta(minutes=30),
            capacity=5
        )

        best_slot = self.foodtruck.get_best_default_pickup_slot()
        self.assertEqual(best_slot, immediate_slot)

    def test_get_best_default_pickup_slot_falls_back_to_current_schedule(self):
        now = self.now
        schedule = ServiceScheduleFactory(
            food_truck=self.foodtruck,
            day_of_week=now.weekday(),
            start_time=(now - timedelta(hours=1)).time(),
            end_time=(now + timedelta(hours=2)).time(),
            is_active=True
        )
        PickupSlotFactory(
            food_truck=self.foodtruck,
            service_schedule=schedule,
            start_time=now + timedelta(minutes=30),
            end_time=now + timedelta(hours=1, minutes=30),
            capacity=5
        )

        slots = self.foodtruck.get_available_slots(now.date())
        best_slot = self.foodtruck.get_best_default_pickup_slot()
        self.assertEqual(best_slot, slots.first())

    def test_get_best_default_pickup_slot_falls_back_to_next_schedule(self):
        # Create next day schedule and slot
        now = self.now
        next_day = (now.weekday() + 1) % 7
        schedule = ServiceScheduleFactory(
            food_truck=self.foodtruck,
            day_of_week=next_day,
            start_time=time(10, 0),
            end_time=time(12, 0),
            is_active=True
        )
        next_day_date = now.date() + timedelta(days=1)
        next_day_slot = PickupSlotFactory(
            food_truck=self.foodtruck,
            service_schedule=schedule,
            start_time=timezone.make_aware(datetime.combine(next_day_date, time(10, 0)), PARIS_TZ),
            end_time=timezone.make_aware(datetime.combine(next_day_date, time(11, 0)), PARIS_TZ),
            capacity=5
        )

        best_slot = self.foodtruck.get_best_default_pickup_slot()
        self.assertEqual(best_slot, next_day_slot)

    def test_get_best_default_pickup_slot_returns_none_when_no_slots(self):
        best_slot = self.foodtruck.get_best_default_pickup_slot()
        self.assertIsNone(best_slot)

    def test_get_best_default_pickup_slot_skips_full_immediate_slot(self):
        now = self.now
        schedule = ServiceScheduleFactory(
            food_truck=self.foodtruck,
            day_of_week=now.weekday(),
            start_time=(now - timedelta(hours=1)).time(),
            end_time=(now + timedelta(hours=2)).time(),
            is_active=True
        )
        immediate_slot = PickupSlotFactory(
            food_truck=self.foodtruck,
            service_schedule=schedule,
            start_time=now - timedelta(minutes=15),
            end_time=now + timedelta(minutes=15),
            capacity=1
        )
        OrderFactory(food_truck=self.foodtruck, pickup_slot=immediate_slot, status='submitted')

        slots = self.foodtruck.get_available_slots(now.date())
        best_slot = self.foodtruck.get_best_default_pickup_slot()
        self.assertEqual(best_slot, slots.first())

    def test_get_best_default_pickup_slot_returns_none_when_slots_are_full(self):
        now = self.now
        schedule = ServiceScheduleFactory(
            food_truck=self.foodtruck,
            day_of_week=now.weekday(),
            start_time=(now - timedelta(hours=1)).time(),
            end_time=(now + timedelta(hours=2)).time(),
            capacity_per_slot=1,
            is_active=True
        )
        slots = self.foodtruck.get_available_slots(now.date())
        for slot in slots:
            OrderFactory(food_truck=self.foodtruck, pickup_slot=slot, status='submitted')

        best_slot = self.foodtruck.get_best_default_pickup_slot()
        self.assertIsNone(best_slot)

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


class FoodTruckServiceScheduleTests(TestCase):
    def test_get_available_slots_generates_once(self):
        foodtruck = FoodTruckFactory()
        schedule = ServiceSchedule.objects.create(
            food_truck=foodtruck,
            day_of_week=(timezone.localdate() + timedelta(days=1)).weekday(),
            start_time=time(9, 0),
            end_time=time(10, 0),
            capacity_per_slot=3,
        )
        target_date = timezone.localdate() + timedelta(days=1)

        first = foodtruck.get_available_slots(target_date)
        second = foodtruck.get_available_slots(target_date)

        self.assertEqual(first.count(), second.count())
        self.assertTrue(first.exists())
        self.assertEqual(first.first().service_schedule_id, schedule.id)
