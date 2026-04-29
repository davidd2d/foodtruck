from decimal import Decimal

import pytz

from django.core.cache import cache
from django.db.models import Avg, Case, CharField, Count, DecimalField, F, IntegerField, Q, Sum, Value, When
from django.db.models.functions import Coalesce, ExtractHour, ExtractWeekDay, TruncDay, TruncMonth, TruncWeek

from orders.models import Order, OrderItem, OrderItemOption, PickupSlot

_LOCAL_TZ = pytz.timezone('Europe/Paris')


class DashboardService:
    """Service layer for owner dashboard analytics."""

    def __init__(self, foodtruck):
        self.foodtruck = foodtruck

    @staticmethod
    def _normalize_category_id(category_id):
        if category_id in (None, ''):
            return None
        try:
            return int(category_id)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _category_filter(category_id, prefix=''):
        normalized = DashboardService._normalize_category_id(category_id)
        if normalized is None:
            return Q()
        item_lookup = f'{prefix}items__item__category_id'
        combo_lookup = f'{prefix}items__combo__category_id'
        return Q(**{item_lookup: normalized}) | Q(**{combo_lookup: normalized})

    def _paid_orders_queryset(self, start_date=None, end_date=None, category_id=None):
        queryset = Order.objects.filter(
            food_truck=self.foodtruck,
            paid_at__isnull=False,
        )
        if start_date:
            queryset = queryset.filter(paid_at__date__gte=start_date)
        if end_date:
            queryset = queryset.filter(paid_at__date__lte=end_date)
        category_filter = self._category_filter(category_id)
        if category_filter:
            queryset = queryset.filter(category_filter).distinct()
        return queryset

    def _slot_paid_order_filter(self, start_date=None, end_date=None, category_id=None):
        order_filter = Q(orders__paid_at__isnull=False)
        if start_date:
            order_filter &= Q(orders__paid_at__date__gte=start_date)
        if end_date:
            order_filter &= Q(orders__paid_at__date__lte=end_date)
        category_filter = self._category_filter(category_id, prefix='orders__')
        if category_filter:
            order_filter &= category_filter
        return order_filter

    def _paid_order_items_queryset(self, start_date=None, end_date=None, category_id=None):
        queryset = OrderItem.objects.filter(
            order__food_truck=self.foodtruck,
            order__paid_at__isnull=False,
        )
        if start_date:
            queryset = queryset.filter(order__paid_at__date__gte=start_date)
        if end_date:
            queryset = queryset.filter(order__paid_at__date__lte=end_date)
        normalized = self._normalize_category_id(category_id)
        if normalized is not None:
            queryset = queryset.filter(
                Q(item__category_id=normalized) | Q(combo__category_id=normalized)
            )
        return queryset

    def _normalize_display_mode(self, display_mode=None):
        allowed = {
            self.foodtruck.PriceDisplayMode.TAX_INCLUDED,
            self.foodtruck.PriceDisplayMode.TAX_EXCLUDED,
        }
        if display_mode in allowed:
            return display_mode
        return self.foodtruck.price_display_mode

    def _display_amount(self, gross, tax, display_mode=None):
        mode = self._normalize_display_mode(display_mode)
        gross = gross or Decimal('0.00')
        tax = tax or Decimal('0.00')
        if mode == self.foodtruck.PriceDisplayMode.TAX_EXCLUDED:
            return (gross - tax).quantize(Decimal('0.01'))
        return gross.quantize(Decimal('0.01'))

    def get_kpis(self, start_date, end_date, category_id=None, display_mode=None):
        """Return core KPI metrics for paid orders in a date window."""
        queryset = self._paid_orders_queryset(start_date=start_date, end_date=end_date, category_id=category_id)
        aggregate = queryset.aggregate(
            total_orders=Count('id'),
            total_revenue_gross=Coalesce(
                Sum('total_amount'),
                Value(Decimal('0.00')),
                output_field=DecimalField(max_digits=12, decimal_places=2),
            ),
            total_revenue_tax=Coalesce(
                Sum('tax_amount'),
                Value(Decimal('0.00')),
                output_field=DecimalField(max_digits=12, decimal_places=2),
            ),
            completed_orders=Count('id', filter=Q(status=Order.Status.COMPLETED)),
        )

        total_orders = aggregate['total_orders'] or 0
        total_revenue = self._display_amount(
            aggregate.get('total_revenue_gross'),
            aggregate.get('total_revenue_tax'),
            display_mode=display_mode,
        )
        completed_orders = aggregate['completed_orders'] or 0

        average_order_value = Decimal('0.00')
        completion_rate = Decimal('0.00')
        if total_orders > 0:
            average_order_value = (total_revenue / Decimal(total_orders)).quantize(Decimal('0.01'))
            completion_rate = (Decimal(completed_orders) * Decimal('100.00') / Decimal(total_orders)).quantize(Decimal('0.01'))

        return {
            'total_orders': total_orders,
            'total_revenue': total_revenue,
            'average_order_value': average_order_value,
            'completion_rate': completion_rate,
        }

    def get_revenue_timeseries(self, start_date, end_date, interval='day', category_id=None, display_mode=None):
        """Return revenue aggregated by day/week/month for paid orders."""
        trunc_map = {
            'day': TruncDay,
            'week': TruncWeek,
            'month': TruncMonth,
        }
        bucket_fn = trunc_map.get(interval, TruncDay)

        rows = (
            self._paid_orders_queryset(start_date=start_date, end_date=end_date, category_id=category_id)
            .annotate(bucket=bucket_fn('paid_at'))
            .values('bucket')
            .annotate(
                revenue_gross=Coalesce(
                    Sum('total_amount'),
                    Value(Decimal('0.00')),
                    output_field=DecimalField(max_digits=12, decimal_places=2),
                ),
                revenue_tax=Coalesce(
                    Sum('tax_amount'),
                    Value(Decimal('0.00')),
                    output_field=DecimalField(max_digits=12, decimal_places=2),
                ),
            )
            .order_by('bucket')
        )

        return [
            {
                'date': row['bucket'].date().isoformat(),
                'revenue': self._display_amount(row.get('revenue_gross'), row.get('revenue_tax'), display_mode=display_mode),
            }
            for row in rows
        ]

    def get_top_items(self, limit=10, start_date=None, end_date=None, category_id=None, display_mode=None):
        """Return top-performing sold items by generated revenue."""
        queryset = self._paid_order_items_queryset(start_date=start_date, end_date=end_date, category_id=category_id)

        rows = (
            queryset.annotate(
                product_name=Case(
                    When(item__isnull=False, then=F('item__name')),
                    When(combo__isnull=False, then=F('combo__name')),
                    default=Value('Unknown item'),
                    output_field=CharField(),
                )
            )
            .values('product_name')
            .annotate(
                quantity_sold=Coalesce(
                    Sum('quantity'),
                    Value(0),
                    output_field=IntegerField(),
                ),
                revenue_generated_gross=Coalesce(
                    Sum('total_price'),
                    Value(Decimal('0.00')),
                    output_field=DecimalField(max_digits=12, decimal_places=2),
                ),
                revenue_generated_tax=Coalesce(
                    Sum('tax_amount'),
                    Value(Decimal('0.00')),
                    output_field=DecimalField(max_digits=12, decimal_places=2),
                ),
            )
            .order_by('-revenue_generated_gross', '-quantity_sold', 'product_name')[:limit]
        )

        data = list(rows)
        for row in data:
            row['revenue_generated'] = self._display_amount(
                row.get('revenue_generated_gross'),
                row.get('revenue_generated_tax'),
                display_mode=display_mode,
            )
        return data

    def get_category_performance(self, start_date=None, end_date=None, limit=8, category_id=None, display_mode=None):
        """Return category-level menu performance for charting."""
        queryset = self._paid_order_items_queryset(start_date=start_date, end_date=end_date, category_id=category_id)

        rows = (
            queryset.annotate(
                category_name=Case(
                    When(item__isnull=False, then=F('item__category__name')),
                    When(combo__isnull=False, then=F('combo__category__name')),
                    default=Value('Uncategorized'),
                    output_field=CharField(),
                )
            )
            .values('category_name')
            .annotate(
                quantity_sold=Coalesce(Sum('quantity'), Value(0), output_field=IntegerField()),
                revenue_generated_gross=Coalesce(
                    Sum('total_price'),
                    Value(Decimal('0.00')),
                    output_field=DecimalField(max_digits=12, decimal_places=2),
                ),
                revenue_generated_tax=Coalesce(
                    Sum('tax_amount'),
                    Value(Decimal('0.00')),
                    output_field=DecimalField(max_digits=12, decimal_places=2),
                ),
            )
            .order_by('-revenue_generated_gross', '-quantity_sold', 'category_name')[:limit]
        )

        data = list(rows)
        for row in data:
            row['revenue_generated'] = self._display_amount(
                row.get('revenue_generated_gross'),
                row.get('revenue_generated_tax'),
                display_mode=display_mode,
            )
        return data

    def get_slot_performance(self, start_date=None, end_date=None, category_id=None):
        """Return slot occupancy metrics for paid orders."""
        slots = self.get_slot_utilization(start_date, end_date, category_id=category_id)

        data = []
        for slot in slots:
            data.append(
                {
                    'slot_id': slot['slot_id'],
                    'slot': slot['slot'],
                    'start_time': slot['start_time'],
                    'end_time': slot['end_time'],
                    'capacity': slot['capacity'],
                    'orders_count': slot['total_orders'],
                    'capacity_usage': slot['utilization_pct'],
                }
            )

        return data

    def get_slot_utilization(self, start_date, end_date, category_id=None):
        """Return paid-order utilization metrics per slot."""
        order_filter = self._slot_paid_order_filter(start_date, end_date, category_id=category_id)
        rows = (
            PickupSlot.objects.filter(food_truck=self.foodtruck)
            .annotate(total_orders=Count('orders', filter=order_filter, distinct=True))
            .order_by('start_time')
            .values('id', 'start_time', 'end_time', 'capacity', 'total_orders')
        )

        return [
            {
                'slot_id': row['id'],
                'slot': f"{row['start_time'].isoformat()} - {row['end_time'].isoformat()}",
                'start_time': row['start_time'],
                'end_time': row['end_time'],
                'total_orders': row['total_orders'],
                'capacity': row['capacity'],
                'utilization_rate': (
                    Decimal(row['total_orders']) / Decimal(row['capacity'])
                    if row['capacity']
                    else Decimal('0.00')
                ).quantize(Decimal('0.0001')),
                'utilization_pct': (
                    Decimal(row['total_orders']) * Decimal('100.00') / Decimal(row['capacity'])
                    if row['capacity']
                    else Decimal('0.00')
                ).quantize(Decimal('0.01')),
            }
            for row in rows
        ]

    def get_revenue_per_slot(self, start_date, end_date, category_id=None, display_mode=None):
        """Return paid-order revenue and average ticket per slot."""
        order_filter = self._slot_paid_order_filter(start_date, end_date, category_id=category_id)
        rows = (
            PickupSlot.objects.filter(food_truck=self.foodtruck)
            .annotate(
                total_orders=Count('orders', filter=order_filter, distinct=True),
                total_revenue_gross=Coalesce(
                    Sum('orders__total_amount', filter=order_filter),
                    Value(Decimal('0.00')),
                    output_field=DecimalField(max_digits=12, decimal_places=2),
                ),
                total_revenue_tax=Coalesce(
                    Sum('orders__tax_amount', filter=order_filter),
                    Value(Decimal('0.00')),
                    output_field=DecimalField(max_digits=12, decimal_places=2),
                ),
                avg_order_value_gross=Coalesce(
                    Avg('orders__total_amount', filter=order_filter),
                    Value(Decimal('0.00')),
                    output_field=DecimalField(max_digits=12, decimal_places=2),
                ),
                avg_order_value_tax=Coalesce(
                    Avg('orders__tax_amount', filter=order_filter),
                    Value(Decimal('0.00')),
                    output_field=DecimalField(max_digits=12, decimal_places=2),
                ),
            )
            .order_by('start_time')
            .values(
                'id',
                'start_time',
                'end_time',
                'total_orders',
                'total_revenue_gross',
                'total_revenue_tax',
                'avg_order_value_gross',
                'avg_order_value_tax',
            )
        )

        return [
            {
                'slot_id': row['id'],
                'slot': f"{row['start_time'].isoformat()} - {row['end_time'].isoformat()}",
                'start_time': row['start_time'],
                'end_time': row['end_time'],
                'total_orders': row['total_orders'],
                'total_revenue': self._display_amount(
                    row.get('total_revenue_gross'),
                    row.get('total_revenue_tax'),
                    display_mode=display_mode,
                ),
                'avg_order_value': self._display_amount(
                    row.get('avg_order_value_gross'),
                    row.get('avg_order_value_tax'),
                    display_mode=display_mode,
                ),
            }
            for row in rows
        ]

    def get_hourly_performance(self, start_date, end_date, category_id=None, display_mode=None):
        """Aggregate paid order performance by pickup slot hour."""
        rows = (
            self._paid_orders_queryset(start_date=start_date, end_date=end_date, category_id=category_id)
            .annotate(hour=ExtractHour('pickup_slot__start_time', tzinfo=_LOCAL_TZ))
            .values('hour')
            .annotate(
                orders=Count('id'),
                revenue_gross=Coalesce(
                    Sum('total_amount'),
                    Value(Decimal('0.00')),
                    output_field=DecimalField(max_digits=12, decimal_places=2),
                ),
                revenue_tax=Coalesce(
                    Sum('tax_amount'),
                    Value(Decimal('0.00')),
                    output_field=DecimalField(max_digits=12, decimal_places=2),
                ),
                avg_order_value_gross=Coalesce(
                    Avg('total_amount'),
                    Value(Decimal('0.00')),
                    output_field=DecimalField(max_digits=12, decimal_places=2),
                ),
                avg_order_value_tax=Coalesce(
                    Avg('tax_amount'),
                    Value(Decimal('0.00')),
                    output_field=DecimalField(max_digits=12, decimal_places=2),
                ),
            )
            .order_by('hour')
        )

        data = list(rows)
        for row in data:
            row['revenue'] = self._display_amount(
                row.get('revenue_gross'),
                row.get('revenue_tax'),
                display_mode=display_mode,
            )
            row['avg_order_value'] = self._display_amount(
                row.get('avg_order_value_gross'),
                row.get('avg_order_value_tax'),
                display_mode=display_mode,
            )
        return data

    def get_weekday_performance(self):
        """Aggregate paid order performance by weekday, Monday=0 ... Sunday=6."""
        weekday_mapped = Case(
            When(weekday_raw=2, then=Value(0)),
            When(weekday_raw=3, then=Value(1)),
            When(weekday_raw=4, then=Value(2)),
            When(weekday_raw=5, then=Value(3)),
            When(weekday_raw=6, then=Value(4)),
            When(weekday_raw=7, then=Value(5)),
            default=Value(6),
            output_field=IntegerField(),
        )

        rows = (
            self._paid_orders_queryset()
            .annotate(weekday_raw=ExtractWeekDay('pickup_slot__start_time', tzinfo=_LOCAL_TZ))
            .annotate(weekday=weekday_mapped)
            .values('weekday')
            .annotate(
                orders=Count('id'),
                revenue=Coalesce(
                    Sum('total_amount'),
                    Value(Decimal('0.00')),
                    output_field=DecimalField(max_digits=12, decimal_places=2),
                ),
            )
            .order_by('weekday')
        )

        return list(rows)

    def get_slot_heatmap(self, start_date, end_date, category_id=None):
        """Return weekday/hour aggregation suitable for heatmap rendering."""
        cache_key = f"dashboard:heatmap:{self.foodtruck.id}:{start_date}:{end_date}:{self._normalize_category_id(category_id) or 'all'}"
        cached = cache.get(cache_key)
        if cached is not None:
            return cached

        weekday_mapped = Case(
            When(weekday_raw=2, then=Value(0)),
            When(weekday_raw=3, then=Value(1)),
            When(weekday_raw=4, then=Value(2)),
            When(weekday_raw=5, then=Value(3)),
            When(weekday_raw=6, then=Value(4)),
            When(weekday_raw=7, then=Value(5)),
            default=Value(6),
            output_field=IntegerField(),
        )

        rows = list(
            self._paid_orders_queryset(start_date=start_date, end_date=end_date, category_id=category_id)
            .annotate(hour=ExtractHour('pickup_slot__start_time', tzinfo=_LOCAL_TZ))
            .annotate(weekday_raw=ExtractWeekDay('pickup_slot__start_time', tzinfo=_LOCAL_TZ))
            .annotate(weekday=weekday_mapped)
            .values('weekday', 'hour')
            .annotate(orders=Count('id'))
            .order_by('weekday', 'hour')
        )

        cache.set(cache_key, rows, 300)
        return rows

    def get_slot_insights(self, category_id=None):
        """Classify slots by utilization ranges for operational insights."""
        utilization_rows = self.get_slot_utilization(start_date=None, end_date=None, category_id=category_id)

        underperforming = [row for row in utilization_rows if row['utilization_pct'] < Decimal('40.00')]
        optimal = [row for row in utilization_rows if Decimal('40.00') <= row['utilization_pct'] <= Decimal('80.00')]
        saturated = [row for row in utilization_rows if row['utilization_pct'] > Decimal('80.00')]

        return {
            'underperforming_slots': underperforming,
            'optimal_slots': optimal,
            'saturated_slots': saturated,
        }

    def get_slot_recommendations(self, category_id=None):
        """Return capacity tuning and new-slot suggestions based on paid-order patterns."""
        cache_key = f"dashboard:slot-reco:{self.foodtruck.id}:{self._normalize_category_id(category_id) or 'all'}"
        cached = cache.get(cache_key)
        if cached is not None:
            return cached

        utilization_rows = self.get_slot_utilization(start_date=None, end_date=None, category_id=category_id)
        increase_capacity_slots = [row for row in utilization_rows if row['utilization_pct'] > Decimal('90.00')]
        reduce_capacity_slots = [row for row in utilization_rows if row['utilization_pct'] < Decimal('30.00')]

        configured_hours = set(
            PickupSlot.objects.filter(food_truck=self.foodtruck).annotate(hour=ExtractHour('start_time', tzinfo=_LOCAL_TZ)).values_list('hour', flat=True)
        )

        from django.utils import timezone
        from datetime import timedelta

        today = timezone.localdate()
        heatmap_rows = self.get_slot_heatmap(today - timedelta(days=29), today, category_id=category_id)

        by_hour = {}
        hour_weekday_orders = {}
        for row in heatmap_rows:
            hour = int(row['hour'])
            weekday = int(row['weekday'])
            orders = int(row['orders'])
            by_hour[hour] = by_hour.get(hour, 0) + orders
            hour_weekday_orders.setdefault(hour, {})
            hour_weekday_orders[hour][weekday] = hour_weekday_orders[hour].get(weekday, 0) + orders

        suggested_new_slots = []
        seen_hours = set()
        for hour, orders in sorted(by_hour.items(), key=lambda entry: entry[1], reverse=True):
            if orders < 2:
                continue

            top_weekdays = sorted(
                hour_weekday_orders.get(hour, {}).items(),
                key=lambda entry: entry[1],
                reverse=True,
            )[:3]
            suggested_weekdays = [weekday for weekday, _ in top_weekdays]

            adjacent_candidates = [hour - 1, hour + 1]
            for candidate in adjacent_candidates:
                if candidate < 0 or candidate > 23:
                    continue
                if candidate in configured_hours or candidate in seen_hours:
                    continue

                suggested_new_slots.append(
                    {
                        'hour': candidate,
                        'source_peak_hour': hour,
                        'demand_orders': orders,
                        'suggested_weekdays': suggested_weekdays,
                    }
                )
                seen_hours.add(candidate)

        payload = {
            'increase_capacity_slots': increase_capacity_slots,
            'reduce_capacity_slots': reduce_capacity_slots,
            'suggested_new_slots': suggested_new_slots,
        }
        cache.set(cache_key, payload, 300)
        return payload

    def get_recent_orders(self, limit=20, start_date=None, end_date=None, category_id=None):
        """Return latest paid orders with related objects preloaded for list rendering."""
        return (
            self._paid_orders_queryset(start_date=start_date, end_date=end_date, category_id=category_id)
            .select_related('pickup_slot', 'user')
            .prefetch_related('items', 'items__item', 'items__combo', 'items__selected_options__option')
            .order_by('-paid_at')[:limit]
        )

    def get_option_performance(self, start_date, end_date, limit=10, category_id=None):
        """Return option analytics: top options by revenue/count + global KPIs."""
        qs = OrderItemOption.objects.filter(
            order_item__order__food_truck=self.foodtruck,
            order_item__order__paid_at__isnull=False,
        )
        if start_date:
            qs = qs.filter(order_item__order__paid_at__date__gte=start_date)
        if end_date:
            qs = qs.filter(order_item__order__paid_at__date__lte=end_date)
        normalized_cat = self._normalize_category_id(category_id)
        if normalized_cat is not None:
            qs = qs.filter(
                Q(order_item__item__category_id=normalized_cat) |
                Q(order_item__combo__category_id=normalized_cat)
            )

        top_options = list(
            qs.values('option__name')
            .annotate(
                selection_count=Count('id'),
                total_revenue=Coalesce(
                    Sum('price_modifier'),
                    Value(Decimal('0.00')),
                    output_field=DecimalField(max_digits=12, decimal_places=2),
                ),
            )
            .order_by('-selection_count', '-total_revenue')[:limit]
        )

        top_paying = list(
            qs.filter(price_modifier__gt=0)
            .values('option__name')
            .annotate(
                selection_count=Count('id'),
                total_revenue=Coalesce(
                    Sum('price_modifier'),
                    Value(Decimal('0.00')),
                    output_field=DecimalField(max_digits=12, decimal_places=2),
                ),
            )
            .order_by('-total_revenue')[:limit]
        )

        totals = qs.aggregate(
            total_option_revenue=Coalesce(
                Sum('price_modifier'),
                Value(Decimal('0.00')),
                output_field=DecimalField(max_digits=12, decimal_places=2),
            ),
        )
        total_option_revenue = totals['total_option_revenue']

        total_paid_orders = self._paid_orders_queryset(
            start_date=start_date, end_date=end_date, category_id=category_id
        ).count()
        orders_with_options = (
            self._paid_orders_queryset(start_date=start_date, end_date=end_date, category_id=category_id)
            .filter(items__selected_options__isnull=False)
            .distinct()
            .count()
        )

        orders_with_options_pct = (
            (Decimal(orders_with_options) * Decimal('100') / Decimal(total_paid_orders)).quantize(Decimal('0.01'))
            if total_paid_orders > 0 else Decimal('0.00')
        )
        avg_option_revenue_per_order = (
            (total_option_revenue / Decimal(total_paid_orders)).quantize(Decimal('0.01'))
            if total_paid_orders > 0 else Decimal('0.00')
        )

        return {
            'top_options': top_options,
            'top_paying_options': top_paying,
            'orders_with_options': orders_with_options,
            'orders_with_options_pct': orders_with_options_pct,
            'total_option_revenue': total_option_revenue,
            'avg_option_revenue_per_order': avg_option_revenue_per_order,
        }
