import logging
from datetime import datetime, timedelta
from decimal import Decimal

from django.core.cache import cache
from django.db.models import Avg, Sum
from django.db.models.functions import ExtractWeekDay
from django.utils import timezone

from analytics.models import EventOpportunity, RevenuePrediction
from orders.models import Order, PickupSlot

logger = logging.getLogger(__name__)


class RevenuePredictionService:
    """Predict daily revenue with deterministic baseline and safe optional AI adjustments."""

    CACHE_TTL_SECONDS = 60 * 30

    def __init__(self, ai_client=None):
        self.ai_client = ai_client

    def predict_day(self, foodtruck, date):
        """Predict one day revenue for a foodtruck with explainable breakdown and fallback."""
        cache_key = f"bi:revenue-day:{foodtruck.id}:{date.isoformat()}"
        cached = cache.get(cache_key)
        if cached is not None:
            return cached

        paid_orders = Order.objects.filter(food_truck=foodtruck, paid_at__isnull=False)
        if not paid_orders.exists():
            fallback = {
                'predicted_revenue': Decimal('120.00'),
                'confidence_score': 0.30,
                'breakdown': {
                    'method': 'fallback_simple_average',
                    'historical_daily_average': 120.0,
                    'weekday_factor': 1.0,
                    'slot_factor': 1.0,
                    'event_factor': 1.0,
                    'ai_adjustment': 0.0,
                },
            }
            RevenuePrediction.objects.create(
                foodtruck=foodtruck,
                date=date,
                predicted_revenue=fallback['predicted_revenue'],
                confidence_score=fallback['confidence_score'],
            )
            cache.set(cache_key, fallback, self.CACHE_TTL_SECONDS)
            logger.info('Revenue prediction fallback used (no data)', extra={'foodtruck_id': foodtruck.id, 'date': str(date)})
            return fallback

        historical_daily_average = self._compute_historical_daily_average(foodtruck)
        weekday_factor = self._compute_weekday_factor(foodtruck, date)
        slot_factor = self._compute_slot_factor(foodtruck, date)
        event_factor = self._compute_event_factor(foodtruck, date)

        deterministic_prediction = historical_daily_average * weekday_factor * slot_factor * event_factor
        ai_adjustment = self._optional_ai_adjustment(foodtruck, date, deterministic_prediction)
        predicted = max(Decimal('0.00'), deterministic_prediction + ai_adjustment).quantize(Decimal('0.01'))

        confidence = self._compute_confidence(foodtruck)
        result = {
            'predicted_revenue': predicted,
            'confidence_score': confidence,
            'breakdown': {
                'method': 'deterministic_with_safe_ai_extension',
                'historical_daily_average': float(historical_daily_average),
                'weekday_factor': float(weekday_factor),
                'slot_factor': float(slot_factor),
                'event_factor': float(event_factor),
                'ai_adjustment': float(ai_adjustment),
            },
        }

        RevenuePrediction.objects.create(
            foodtruck=foodtruck,
            date=date,
            predicted_revenue=predicted,
            confidence_score=confidence,
        )

        cache.set(cache_key, result, self.CACHE_TTL_SECONDS)
        logger.info(
            'Revenue prediction computed',
            extra={'foodtruck_id': foodtruck.id, 'date': str(date), 'result': result},
        )
        return result

    def enqueue_prediction(self, foodtruck, date):
        """Future-ready async entrypoint currently running synchronously."""
        return self.predict_day(foodtruck, date)

    def _compute_historical_daily_average(self, foodtruck):
        rows = (
            Order.objects.filter(food_truck=foodtruck, paid_at__isnull=False)
            .values('paid_at__date')
            .annotate(total=Sum('total_amount'))
        )
        if not rows:
            return Decimal('120.00')
        total = sum((row['total'] or Decimal('0.00')) for row in rows)
        return (Decimal(total) / Decimal(len(rows))).quantize(Decimal('0.01'))

    def _compute_weekday_factor(self, foodtruck, target_date):
        weekday = target_date.weekday()
        rows = (
            Order.objects.filter(food_truck=foodtruck, paid_at__isnull=False)
            .annotate(dow=ExtractWeekDay('paid_at'))
            .values('dow')
            .annotate(avg=Avg('total_amount'))
        )
        global_avg = Order.objects.filter(food_truck=foodtruck, paid_at__isnull=False).aggregate(avg=Avg('total_amount')).get('avg')
        global_avg = Decimal(global_avg or '1.00')

        lookup = {}
        for row in rows:
            try:
                dow = int(row['dow'])
            except (TypeError, ValueError):
                continue
            # Django ExtractWeekDay: Sunday=1 ... Saturday=7 => Monday index conversion.
            monday_based = 6 if dow == 1 else dow - 2
            lookup[monday_based] = Decimal(row['avg'] or '0.00')

        weekday_avg = lookup.get(weekday)
        if weekday_avg is None or global_avg <= 0:
            return Decimal('1.00')
        factor = weekday_avg / global_avg
        return max(Decimal('0.70'), min(Decimal('1.35'), factor))

    def _compute_slot_factor(self, foodtruck, target_date):
        slot_count = PickupSlot.objects.filter(food_truck=foodtruck, start_time__date=target_date).count()
        if slot_count == 0:
            return Decimal('0.90')
        if slot_count <= 8:
            return Decimal('1.00')
        if slot_count <= 16:
            return Decimal('1.08')
        return Decimal('1.15')

    def _compute_event_factor(self, foodtruck, target_date):
        opportunities = EventOpportunity.objects.filter(
            foodtruck=foodtruck,
            event__start_date__lte=target_date,
            event__end_date__gte=target_date,
        )
        if not opportunities.exists():
            return Decimal('1.00')

        best_score = opportunities.order_by('-opportunity_score').values_list('opportunity_score', flat=True).first() or 0
        normalized = Decimal(str(best_score)) / Decimal('100.00')
        return max(Decimal('1.00'), min(Decimal('1.40'), Decimal('1.00') + normalized * Decimal('0.40')))

    def _compute_confidence(self, foodtruck):
        recent_count = Order.objects.filter(
            food_truck=foodtruck,
            paid_at__isnull=False,
            paid_at__gte=timezone.now() - timedelta(days=60),
        ).count()
        if recent_count >= 120:
            return 0.9
        if recent_count >= 60:
            return 0.75
        if recent_count >= 20:
            return 0.6
        return 0.45

    def _optional_ai_adjustment(self, foodtruck, target_date, deterministic_prediction):
        if self.ai_client is None:
            return Decimal('0.00')

        try:
            prompt = (
                'Adjust one-day revenue prediction for a food truck. Return only number between -50 and 50. '\
                f'foodtruck={foodtruck.name}, date={target_date.isoformat()}, '\
                f'deterministic_prediction={float(deterministic_prediction):.2f}'
            )
            raw = self.ai_client.generate(prompt=prompt, use_cache=True, max_tokens=20)
            adjustment = Decimal(str(float(raw.strip())))
            return max(Decimal('-50.00'), min(Decimal('50.00'), adjustment))
        except Exception:
            logger.warning('AI revenue adjustment failed; deterministic fallback used', exc_info=True)
            return Decimal('0.00')
