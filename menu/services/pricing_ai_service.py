import logging
from datetime import timedelta
from decimal import Decimal

from django.core.cache import cache
from django.db.models import Avg, Count
from django.utils import timezone

from menu.models import PricingSuggestion
from orders.models import OrderItem

logger = logging.getLogger(__name__)


class PricingAIService:
    """Suggests prices from deterministic signals with safe optional AI adjustment."""

    CACHE_TTL_SECONDS = 60 * 30

    def __init__(self, ai_client=None):
        self.ai_client = ai_client

    def suggest_price(self, item):
        """Return a non-blocking, explainable pricing suggestion for one item."""
        cache_key = f"bi:pricing:{item.id}"
        cached = cache.get(cache_key)
        if cached is not None:
            return cached

        current_price = item.base_price
        now = timezone.now()
        sales = OrderItem.objects.filter(
            item=item,
            order__paid_at__isnull=False,
            order__paid_at__gte=now - timedelta(days=30),
        )

        sales_volume = sales.aggregate(total=Count('id')).get('total') or 0
        avg_ticket_impact = sales.aggregate(avg=Avg('total_price')).get('avg') or current_price
        avg_ticket_impact = Decimal(avg_ticket_impact)

        category_name = item.category.name.lower() if item.category_id else 'other'
        category_factor = self._category_factor(category_name)
        demand_factor = self._demand_factor(sales_volume)
        time_factor = self._time_factor(now.hour)

        deterministic_price = current_price * category_factor * demand_factor * time_factor
        ai_adjustment = self._optional_ai_adjustment(item, deterministic_price)
        suggested_price = max(Decimal('0.50'), deterministic_price + ai_adjustment).quantize(Decimal('0.01'))

        confidence = self._confidence_from_volume(sales_volume)
        reason = (
            f"Current price {current_price:.2f} EUR, sales volume {sales_volume} in last 30 days, "
            f"category factor {float(category_factor):.2f}, demand factor {float(demand_factor):.2f}, "
            f"time factor {float(time_factor):.2f}, average line value {float(avg_ticket_impact):.2f}."
        )

        PricingSuggestion.objects.create(
            item=item,
            suggested_price=suggested_price,
            current_price=current_price,
            confidence_score=confidence,
            reason=reason,
        )

        payload = {
            'suggested_price': suggested_price,
            'current_price': current_price,
            'confidence_score': confidence,
            'reason': reason,
            'breakdown': {
                'sales_volume': sales_volume,
                'category_factor': float(category_factor),
                'demand_factor': float(demand_factor),
                'time_factor': float(time_factor),
                'ai_adjustment': float(ai_adjustment),
            },
        }

        cache.set(cache_key, payload, self.CACHE_TTL_SECONDS)
        logger.info(
            'Pricing suggestion generated',
            extra={'item_id': item.id, 'foodtruck_id': item.category.menu.food_truck_id, 'payload': payload},
        )
        return payload

    def enqueue_suggestion(self, item):
        """Future-ready async entrypoint currently running synchronously."""
        return self.suggest_price(item)

    def _category_factor(self, category_name):
        if any(token in category_name for token in ['drink', 'boisson']):
            return Decimal('1.03')
        if any(token in category_name for token in ['dessert']):
            return Decimal('1.05')
        if any(token in category_name for token in ['pizza', 'burger', 'sandwich', 'taco']):
            return Decimal('1.08')
        return Decimal('1.02')

    def _demand_factor(self, sales_volume):
        if sales_volume >= 120:
            return Decimal('1.12')
        if sales_volume >= 60:
            return Decimal('1.07')
        if sales_volume >= 20:
            return Decimal('1.03')
        return Decimal('0.97')

    def _time_factor(self, hour):
        if 11 <= hour <= 14 or 18 <= hour <= 21:
            return Decimal('1.03')
        return Decimal('0.99')

    def _confidence_from_volume(self, sales_volume):
        if sales_volume >= 120:
            return 0.92
        if sales_volume >= 60:
            return 0.82
        if sales_volume >= 20:
            return 0.68
        return 0.45

    def _optional_ai_adjustment(self, item, deterministic_price):
        if self.ai_client is None:
            return Decimal('0.00')

        try:
            prompt = (
                'Adjust a menu item suggested price. Return only a numeric value between -1.5 and 1.5. '\
                f'item={item.name}, category={item.category.name}, deterministic_price={float(deterministic_price):.2f}, '\
                f'current_price={float(item.base_price):.2f}'
            )
            raw = self.ai_client.generate(prompt=prompt, use_cache=True, max_tokens=20)
            adjustment = Decimal(str(float(raw.strip())))
            return max(Decimal('-1.50'), min(Decimal('1.50'), adjustment))
        except Exception:
            logger.warning('AI pricing adjustment failed; deterministic fallback used', exc_info=True)
            return Decimal('0.00')
