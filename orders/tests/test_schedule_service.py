from datetime import time, timedelta
import pytz

from django.test import TestCase
from django.utils import timezone

from orders.models import ServiceSchedule, PickupSlot, PARIS_TZ
from orders.services.schedule_service import generate_slots_for_date
from orders.tests.factories import FoodTruckFactory


class ScheduleServiceTests(TestCase):
    def _future_date(self, days=1):
        return timezone.localdate() + timedelta(days=days)

    def _slot_times(self, start, end, duration):
        slots = []
        current = start
        while current + duration <= end:
            slots.append(current)
            current += duration
        return slots

    def test_lunch_schedule_generates_expected_slots(self):
        truck = FoodTruckFactory()
        target_date = self._future_date()
        schedule = ServiceSchedule.objects.create(
            food_truck=truck,
            day_of_week=target_date.weekday(),
            start_time=time(12, 0),
            end_time=time(14, 0),
            capacity_per_slot=4,
            slot_duration_minutes=10,
        )
        generated = generate_slots_for_date(truck, target_date)
        self.assertEqual(
            len(generated),
            12,
            f"Lunch schedule should create 12 slots, got {len(generated)}",
        )
        self.assertEqual(
            generated[0].start_time.hour,
            12,
            "First lunch slot should start at 12:00",
        )
        self.assertEqual(
            generated[-1].end_time.hour,
            14,
            "Last lunch slot should end at 14:00",
        )

    def test_dinner_schedule_generates_expected_slots(self):
        truck = FoodTruckFactory()
        target_date = self._future_date(2)
        schedule = ServiceSchedule.objects.create(
            food_truck=truck,
            day_of_week=target_date.weekday(),
            start_time=time(19, 0),
            end_time=time(22, 0),
            capacity_per_slot=5,
            slot_duration_minutes=10,
        )
        generated = generate_slots_for_date(truck, target_date)
        self.assertEqual(
            len(generated),
            18,
            f"Dinner schedule should create 18 slots, got {len(generated)}",
        )
        self.assertEqual(
            generated[0].start_time.hour,
            19,
            "Dinner slots should begin at 19:00",
        )
        self.assertEqual(
            generated[-1].end_time.hour,
            22,
            "Dinner slots should end at 22:00",
        )

    def test_lunch_and_dinner_generate_combined_slots(self):
        truck = FoodTruckFactory()
        target_date = self._future_date(3)
        ServiceSchedule.objects.create(
            food_truck=truck,
            day_of_week=target_date.weekday(),
            start_time=time(12, 0),
            end_time=time(14, 0),
            capacity_per_slot=4,
            slot_duration_minutes=10,
        )
        ServiceSchedule.objects.create(
            food_truck=truck,
            day_of_week=target_date.weekday(),
            start_time=time(19, 0),
            end_time=time(22, 0),
            capacity_per_slot=5,
            slot_duration_minutes=10,
        )
        generated = generate_slots_for_date(truck, target_date)
        self.assertEqual(
            len(generated),
            30,
            f"Lunch + dinner should create 30 slots, got {len(generated)}",
        )

    def test_generation_is_idempotent(self):
        truck = FoodTruckFactory()
        target_date = self._future_date(4)
        schedule = ServiceSchedule.objects.create(
            food_truck=truck,
            day_of_week=target_date.weekday(),
            start_time=time(9, 0),
            end_time=time(11, 0),
            capacity_per_slot=3,
            slot_duration_minutes=15,
        )
        first = generate_slots_for_date(truck, target_date)
        second = generate_slots_for_date(truck, target_date)
        self.assertEqual(
            len(second),
            0,
            "Second generation should not return new slots",
        )

    def test_past_schedules_do_not_create_slots(self):
        truck = FoodTruckFactory()
        target_date = timezone.localdate()
        schedule = ServiceSchedule.objects.create(
            food_truck=truck,
            day_of_week=target_date.weekday(),
            start_time=time(1, 0),
            end_time=time(2, 0),
            capacity_per_slot=2,
            slot_duration_minutes=15,
        )
        generated = generate_slots_for_date(truck, target_date)
        self.assertTrue(
            all(slot.start_time >= timezone.localtime(timezone.now(), PARIS_TZ) for slot in generated),
            "Slots generated today must be in the future",
        )

    def test_inactive_schedule_is_skipped(self):
        truck = FoodTruckFactory()
        target_date = self._future_date(5)
        schedule = ServiceSchedule.objects.create(
            food_truck=truck,
            day_of_week=target_date.weekday(),
            start_time=time(9, 0),
            end_time=time(10, 0),
            capacity_per_slot=2,
            slot_duration_minutes=15,
            is_active=False,
        )
        generated = generate_slots_for_date(truck, target_date)
        self.assertEqual(
            len(generated),
            0,
            "Inactive schedules should not generate slots",
        )
