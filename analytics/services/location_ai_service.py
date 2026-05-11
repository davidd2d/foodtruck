import logging
from datetime import timedelta
from decimal import Decimal

from django.core.cache import cache
from django.db.models import Avg, Count, Q
from django.utils import timezone

from analytics.models import Event
from foodtrucks.models import LocationScore
from orders.models import Order, PickupSlot

logger = logging.getLogger(__name__)


class LocationAIService:
    """Hybrid location intelligence: deterministic heuristics + optional AI adjustments."""

    CACHE_TTL_SECONDS = 60 * 15

    def __init__(self, foodtruck, ai_client=None):
        self.foodtruck = foodtruck
        self.ai_client = ai_client

    def compute_score(self, lat, lng):
        """Compute a location score (0-100) with explainable deterministic breakdown."""
        cache_key = f"bi:location-score:{self.foodtruck.id}:{round(float(lat), 4)}:{round(float(lng), 4)}"
        cached = cache.get(cache_key)
        if cached is not None:
            return cached

        demand_score = self._compute_demand_score(lat, lng)
        competition_score = self._compute_competition_score(lat, lng)
        event_score = self._compute_event_score(lat, lng)

        base_score = (
            demand_score * Decimal('0.50')
            + competition_score * Decimal('0.30')
            + event_score * Decimal('0.20')
        )
        ai_adjustment = self._compute_optional_ai_adjustment(lat, lng, demand_score, competition_score, event_score)
        final_score = max(Decimal('0.00'), min(Decimal('100.00'), base_score + ai_adjustment))

        payload = {
            'score': float(final_score.quantize(Decimal('0.01'))),
            'breakdown': {
                'demand_score': float(demand_score.quantize(Decimal('0.01'))),
                'competition_score': float(competition_score.quantize(Decimal('0.01'))),
                'event_score': float(event_score.quantize(Decimal('0.01'))),
                'ai_adjustment': float(ai_adjustment.quantize(Decimal('0.01'))),
                'method': 'deterministic_with_safe_ai_extension',
            },
        }

        LocationScore.objects.create(
            foodtruck=self.foodtruck,
            latitude=Decimal(str(round(float(lat), 6))),
            longitude=Decimal(str(round(float(lng), 6))),
            score=payload['score'],
            demand_score=payload['breakdown']['demand_score'],
            competition_score=payload['breakdown']['competition_score'],
            event_score=payload['breakdown']['event_score'],
        )

        cache.set(cache_key, payload, self.CACHE_TTL_SECONDS)
        logger.info(
            'Location score computed',
            extra={
                'foodtruck_id': self.foodtruck.id,
                'latitude': float(lat),
                'longitude': float(lng),
                'score': payload['score'],
                'breakdown': payload['breakdown'],
            },
        )
        return payload

    def find_best_spots(self, foodtruck=None):
        """Return top suggested nearby spots around the truck base location."""
        target_foodtruck = foodtruck or self.foodtruck
        base_lat = float(target_foodtruck.latitude)
        base_lng = float(target_foodtruck.longitude)
        offsets = [
            (0.0, 0.0),
            (0.01, 0.00),
            (-0.01, 0.00),
            (0.00, 0.01),
            (0.00, -0.01),
            (0.015, 0.015),
            (-0.015, 0.015),
            (0.015, -0.015),
        ]

        scored = []
        for lat_offset, lng_offset in offsets:
            lat = base_lat + lat_offset
            lng = base_lng + lng_offset
            result = self.compute_score(lat, lng)
            scored.append({
                'latitude': lat,
                'longitude': lng,
                'score': result['score'],
                'breakdown': result['breakdown'],
            })

        scored.sort(key=lambda entry: entry['score'], reverse=True)
        top = scored[:3]
        logger.info(
            'Best spots generated',
            extra={'foodtruck_id': target_foodtruck.id, 'spots_count': len(top)},
        )
        return top

    def enqueue_refresh(self):
        """Future-ready async hook: kept synchronous for now."""
        return self.find_best_spots(self.foodtruck)

    def _compute_demand_score(self, lat, lng):
        now = timezone.now()
        recent_orders = Order.objects.filter(
            food_truck=self.foodtruck,
            paid_at__isnull=False,
            paid_at__gte=now - timedelta(days=30),
        )
        if not recent_orders.exists():
            return Decimal('50.00')

        order_count = recent_orders.count()
        avg_amount = recent_orders.aggregate(avg=Avg('total_amount')).get('avg') or Decimal('0.00')

        nearby_slots = PickupSlot.objects.filter(
            food_truck=self.foodtruck,
            start_time__gte=now - timedelta(days=30),
        ).annotate(
            paid_orders=Count('orders', filter=Q(orders__paid_at__isnull=False)),
        )
        avg_slot_utilization = Decimal('0.00')
        if nearby_slots.exists():
            total_capacity = sum(slot.capacity for slot in nearby_slots)
            total_bookings = sum(slot.paid_orders for slot in nearby_slots)
            if total_capacity > 0:
                avg_slot_utilization = Decimal(total_bookings) / Decimal(total_capacity)

        day_hour_pattern = self._compute_time_pattern_multiplier(now)

        count_component = min(Decimal('100.00'), Decimal(order_count) * Decimal('2.00'))
        revenue_component = min(Decimal('100.00'), Decimal(avg_amount) * Decimal('4.00'))
        utilization_component = min(Decimal('100.00'), avg_slot_utilization * Decimal('100.00'))

        score = (count_component * Decimal('0.4')) + (revenue_component * Decimal('0.3')) + (utilization_component * Decimal('0.3'))
        score *= day_hour_pattern
        return max(Decimal('0.00'), min(Decimal('100.00'), score))

    def _compute_competition_score(self, lat, lng):
        competitors = (
            self.foodtruck.__class__.objects
            .get_queryset()
            .active()
            .nearby(float(lat), float(lng), radius_km=2)
            .exclude(pk=self.foodtruck.pk)
        )
        competitor_count = competitors.count()
        if competitor_count == 0:
            return Decimal('90.00')
        penalty = min(Decimal('70.00'), Decimal(competitor_count) * Decimal('12.00'))
        return max(Decimal('20.00'), Decimal('100.00') - penalty)

    def _compute_event_score(self, lat, lng):
        today = timezone.localdate()
        events = Event.objects.filter(start_date__lte=today + timedelta(days=7), end_date__gte=today)
        if not events.exists():
            return Decimal('40.00')

        best = Decimal('0.00')
        for event in events:
            distance_km = self.foodtruck.distance_to(event.latitude, event.longitude)
            if distance_km > 20:
                continue
            distance_factor = max(Decimal('0.00'), Decimal('1.00') - (Decimal(str(distance_km)) / Decimal('20.00')))
            attendance = Decimal(event.expected_attendance or 500)
            attendance_factor = min(Decimal('1.00'), attendance / Decimal('5000.00'))
            score = (distance_factor * Decimal('70.00')) + (attendance_factor * Decimal('30.00'))
            best = max(best, score)

        if best == Decimal('0.00'):
            return Decimal('35.00')
        return max(Decimal('0.00'), min(Decimal('100.00'), best))

    def _compute_time_pattern_multiplier(self, now):
        weekday = now.weekday()
        hour = now.hour
        weekday_boost = Decimal('1.05') if weekday in (4, 5, 6) else Decimal('0.95')
        hour_boost = Decimal('1.10') if 11 <= hour <= 14 or 18 <= hour <= 21 else Decimal('0.90')
        return weekday_boost * hour_boost

    def _compute_optional_ai_adjustment(self, lat, lng, demand_score, competition_score, event_score):
        """Safe optional AI adjustment. Returns 0 on any issue."""
        if self.ai_client is None:
            return Decimal('0.00')

        try:
            prompt = (
                'You are an assistant adjusting a location score for food-truck deployment. '
                'Return only a number between -5 and 5. '\
                f'demand={float(demand_score):.2f}, competition={float(competition_score):.2f}, '\
                f'event={float(event_score):.2f}, lat={float(lat):.6f}, lng={float(lng):.6f}'
            )
            raw = self.ai_client.generate(prompt=prompt, use_cache=True, max_tokens=20)
            adjustment = Decimal(str(float(raw.strip())))
            return max(Decimal('-5.00'), min(Decimal('5.00'), adjustment))
        except Exception:
            logger.warning('AI location adjustment failed; deterministic fallback used', exc_info=True)
            return Decimal('0.00')
