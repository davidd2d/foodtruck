import logging
from datetime import timedelta
from decimal import Decimal

from django.core.cache import cache
from django.db.models import Avg, Count, Sum
from django.utils import timezone

from analytics.models import EventOpportunity
from orders.models import Order

logger = logging.getLogger(__name__)


class EventAIService:
    """Event opportunity intelligence with deterministic scoring and explainability."""

    CACHE_TTL_SECONDS = 60 * 20

    def __init__(self, ai_client=None):
        self.ai_client = ai_client

    def evaluate_event(self, foodtruck, event):
        """Return opportunity score and predicted revenue for one foodtruck/event pair."""
        cache_key = f"bi:event:{foodtruck.id}:{event.id}"
        cached = cache.get(cache_key)
        if cached is not None:
            return cached

        distance_km = Decimal(str(foodtruck.distance_to(event.latitude, event.longitude)))
        distance_score = self._distance_score(distance_km)
        attendance_score = self._attendance_score(event.expected_attendance)
        category_match_score = self._category_match_score(foodtruck)
        timing_score = self._timing_score(event)

        base_score = (
            distance_score * Decimal('0.35')
            + attendance_score * Decimal('0.30')
            + category_match_score * Decimal('0.20')
            + timing_score * Decimal('0.15')
        )

        ai_adjustment = self._optional_ai_adjustment(foodtruck, event, base_score)
        opportunity_score = max(Decimal('0.00'), min(Decimal('100.00'), base_score + ai_adjustment))
        predicted_revenue = self._predict_revenue(foodtruck, opportunity_score, event)

        EventOpportunity.objects.create(
            foodtruck=foodtruck,
            event=event,
            opportunity_score=float(opportunity_score.quantize(Decimal('0.01'))),
            predicted_revenue=predicted_revenue,
        )

        payload = {
            'opportunity_score': float(opportunity_score.quantize(Decimal('0.01'))),
            'predicted_revenue': predicted_revenue,
            'breakdown': {
                'distance_score': float(distance_score.quantize(Decimal('0.01'))),
                'attendance_score': float(attendance_score.quantize(Decimal('0.01'))),
                'category_match_score': float(category_match_score.quantize(Decimal('0.01'))),
                'timing_score': float(timing_score.quantize(Decimal('0.01'))),
                'ai_adjustment': float(ai_adjustment.quantize(Decimal('0.01'))),
                'distance_km': float(distance_km.quantize(Decimal('0.01'))),
            },
        }

        logger.info(
            'Event opportunity evaluated',
            extra={
                'foodtruck_id': foodtruck.id,
                'event_id': event.id,
                'result': payload,
            },
        )
        cache.set(cache_key, payload, self.CACHE_TTL_SECONDS)
        return payload

    def _distance_score(self, distance_km):
        if distance_km <= Decimal('1.00'):
            return Decimal('100.00')
        if distance_km >= Decimal('30.00'):
            return Decimal('10.00')
        ratio = Decimal('1.00') - ((distance_km - Decimal('1.00')) / Decimal('29.00'))
        return max(Decimal('10.00'), min(Decimal('100.00'), ratio * Decimal('100.00')))

    def _attendance_score(self, expected_attendance):
        attendance = Decimal(expected_attendance or 500)
        normalized = min(Decimal('1.00'), attendance / Decimal('10000.00'))
        return normalized * Decimal('100.00')

    def _category_match_score(self, foodtruck):
        item_names = list(
            foodtruck.menus.filter(is_active=True)
            .values_list('categories__items__name', flat=True)
        )
        lower_names = ' '.join(name.lower() for name in item_names if name)
        if any(token in lower_names for token in ['burger', 'pizza', 'taco', 'bowl', 'sandwich']):
            return Decimal('75.00')
        return Decimal('55.00')

    def _timing_score(self, event):
        duration_days = max(1, (event.end_date - event.start_date).days + 1)
        if duration_days == 1:
            return Decimal('85.00')
        if duration_days <= 3:
            return Decimal('75.00')
        return Decimal('65.00')

    def _predict_revenue(self, foodtruck, opportunity_score, event):
        recent_orders = Order.objects.filter(
            food_truck=foodtruck,
            paid_at__isnull=False,
            paid_at__gte=timezone.now() - timedelta(days=30),
        )

        if recent_orders.exists():
            aggregates = recent_orders.aggregate(
                avg_order=Avg('total_amount'),
                total_revenue=Sum('total_amount'),
            )
            avg_order = Decimal(str(aggregates.get('avg_order') or Decimal('12.00')))
            total_revenue = Decimal(str(aggregates.get('total_revenue') or Decimal('0.00')))
            active_days = max(1, recent_orders.values('paid_at__date').distinct().count())
            recent_daily_revenue = total_revenue / Decimal(active_days)
        else:
            avg_order = Decimal('12.00')
            recent_daily_revenue = Decimal('180.00')

        attendance = Decimal(str(event.expected_attendance or 500))
        duration_days = Decimal(str(max(1, (event.end_date - event.start_date).days + 1)))
        score_scale = Decimal(str(opportunity_score)) / Decimal('100.00')

        attendance_factor = max(Decimal('0.80'), min(Decimal('2.50'), attendance / Decimal('1200.00')))
        duration_factor = Decimal('1.00') + min(duration_days - Decimal('1.00'), Decimal('4.00')) * Decimal('0.10')
        conversion_rate = Decimal('0.008') + (score_scale * Decimal('0.020'))

        demand_revenue = attendance * avg_order * conversion_rate * duration_factor
        baseline_revenue = recent_daily_revenue * duration_factor * attendance_factor
        predicted = (baseline_revenue * Decimal('0.45')) + (demand_revenue * Decimal('0.55'))
        predicted = max(Decimal('25.00'), predicted)
        return predicted.quantize(Decimal('0.01'))

    def _optional_ai_adjustment(self, foodtruck, event, base_score):
        if self.ai_client is None:
            return Decimal('0.00')

        try:
            prompt = (
                'Adjust event opportunity score for a food truck. Return only number between -5 and 5. '\
                f'base_score={float(base_score):.2f}, event_name={event.name}, '\
                f'attendance={event.expected_attendance or 0}, start={event.start_date}, end={event.end_date}, '\
                f'foodtruck={foodtruck.name}'
            )
            raw = self.ai_client.generate(prompt=prompt, use_cache=True, max_tokens=20)
            adjustment = Decimal(str(float(raw.strip())))
            return max(Decimal('-5.00'), min(Decimal('5.00'), adjustment))
        except Exception:
            logger.warning('AI event adjustment failed; deterministic fallback used', exc_info=True)
            return Decimal('0.00')
