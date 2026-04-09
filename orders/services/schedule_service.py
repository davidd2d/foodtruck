from datetime import datetime, timedelta
from typing import List
import logging

from django.utils import timezone

from orders.models import PickupSlot, ServiceSchedule, PARIS_TZ

logger = logging.getLogger(__name__)

def generate_slots_for_date(food_truck, target_date) -> List[PickupSlot]:
    """
    Generate pickup slots for the given date based on active schedules.

    The method is idempotent: slots already created for the same schedule and start
    time are not duplicated. Slots in the past (Europe/Paris time) are skipped.
    """
    if not hasattr(target_date, 'weekday'):
        raise TypeError("target_date must be a date instance.")

    local_now = timezone.localtime(timezone.now(), PARIS_TZ)
    logger.info(
        "Generating slots for food_truck=%s target_date=%s paris_now=%s",
        getattr(food_truck, 'id', None),
        target_date,
        local_now,
    )

    if target_date < local_now.date():
        logger.info("Target date %s is in the past, skipping generation", target_date)
        return []

    schedules = ServiceSchedule.objects.filter(
        food_truck=food_truck,
        day_of_week=target_date.weekday(),
        is_active=True
    ).order_by('start_time')
    logger.info("Found %s active schedules for date %s", schedules.count(), target_date)

    existing_starts = set(PickupSlot.objects.filter(
        food_truck=food_truck,
        start_time__date=target_date
    ).values_list('start_time', flat=True))

    slots_to_create = []
    for schedule in schedules:
        if not schedule.slot_duration_minutes or schedule.slot_duration_minutes <= 0:
            logger.warning(
                "Schedule %s has invalid slot_duration_minutes=%s, skipping",
                schedule.id,
                schedule.slot_duration_minutes,
            )
            continue

        start_dt = timezone.make_aware(
            datetime.combine(target_date, schedule.start_time),
            PARIS_TZ
        )
        end_dt = timezone.make_aware(
            datetime.combine(target_date, schedule.end_time),
            PARIS_TZ
        )

        if end_dt <= start_dt:
            logger.warning(
                "Schedule %s has end_dt <= start_dt (%s <= %s), skipping",
                schedule.id,
                end_dt,
                start_dt,
            )
            continue

        slot_duration = timedelta(minutes=schedule.slot_duration_minutes)
        current = start_dt
        schedule_slots = 0
        logger.info(
            "Processing schedule=%s start=%s end=%s slot_duration=%s capacity=%s",
            schedule.id,
            start_dt,
            end_dt,
            slot_duration,
            schedule.capacity_per_slot,
        )
        while current + slot_duration <= end_dt:
            slot_end = current + slot_duration
            if slot_end <= local_now:
                logger.debug("Skipping past slot at %s", current)
                current += slot_duration
                continue

            if current not in existing_starts:
                slots_to_create.append(PickupSlot(
                    food_truck=food_truck,
                    start_time=current,
                    end_time=slot_end,
                    capacity=schedule.capacity_per_slot,
                    service_schedule=schedule,
                ))
                existing_starts.add(current)
                schedule_slots += 1
            else:
                logger.debug("Slot at %s already exists, skipping", current)

            current += slot_duration

        logger.info("Schedule %s generated %s new slots", schedule.id, schedule_slots)

    if slots_to_create:
        try:
            created = PickupSlot.objects.bulk_create(slots_to_create)
        except Exception as exc:
            logger.exception("Failed to bulk create pickup slots: %s", exc)
            raise
        logger.info("Created %s pickup slots for date %s", len(created), target_date)
        return created

    logger.info("No new pickup slots needed for %s", target_date)
    return []
