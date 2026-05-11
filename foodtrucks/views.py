from datetime import date, timedelta
import logging
import unicodedata
import urllib.parse
import urllib.request
import json

from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, render
from django.views.generic import TemplateView, View
from django.utils import timezone
from django.db.models import Q
from django.core.cache import cache
from django.utils.translation import gettext_lazy as _

logger = logging.getLogger(__name__)

from .models import FoodTruck
from analytics.models import Event
from analytics.models import EventAIAnalysis
from analytics.services import (
    DashboardService,
    EventAIService,
    LocationAIService,
    RevenuePredictionService,
)
from analytics.services.feature_extraction import EventFeatureExtractor
from analytics.services.schemas import validate_and_normalize
from analytics.services.scoring import EventScoringService, explain_score
from analytics.tasks.analyze_event import analyze_event_task
from analytics.services.prompts import CURRENT_PROMPT_VERSION
from menu.services import PricingAIService
from menu.services.menu_service import MenuService

# Create your views here.


def foodtruck_list(request):
    """
    Display list of foodtrucks.
    Business logic is handled by JavaScript via API calls.
    """
    return render(request, 'foodtrucks/list.html')


def foodtruck_detail(request, slug):
    """
    Render the foodtruck detail page for the requested slug.
    """
    foodtruck = get_object_or_404(
        FoodTruck.objects.select_related('subscription__plan').prefetch_related('supported_preferences'),
        slug=slug,
        is_active=True,
    )

    # Check if debug mode is requested
    use_debug = request.GET.get('debug') == '1'
    categories = []
    available_slots = []
    default_slot_id = None
    try:
        menu = MenuService.get_active_menu_for_foodtruck(foodtruck.slug)
        categories = menu.categories.order_by('display_order', 'name')
    except Http404:
        categories = []

    if foodtruck.can_accept_orders():
        available_slots = list(foodtruck.get_recommended_pickup_slots())
        if available_slots:
            default_slot_id = available_slots[0].id

    return render(
        request,
        'foodtrucks/detail_debug.html' if use_debug else 'foodtrucks/detail.html',
        {
            'foodtruck': foodtruck,
            'categories': categories,
            'available_pickup_slots': available_slots,
            'default_pickup_slot_id': default_slot_id,
        }
    )


def _load_menu_categories(foodtruck):
    try:
        menu = MenuService.get_active_menu_for_foodtruck(foodtruck.slug)
    except Http404:
        return []
    return menu.categories.order_by('display_order', 'name')


def _parse_iso_date(value):
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def _parse_category_id(request):
    raw = request.GET.get('category_id')
    if raw in (None, ''):
        return None
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def _parse_display_mode(request, foodtruck):
    raw = request.GET.get('display_mode')
    allowed = {
        FoodTruck.PriceDisplayMode.TAX_INCLUDED,
        FoodTruck.PriceDisplayMode.TAX_EXCLUDED,
    }
    if raw in allowed:
        return raw
    return foodtruck.price_display_mode


def _reverse_geocode_location(latitude, longitude):
    """Return a human-readable location from coordinates using cached reverse geocoding."""
    if latitude is None or longitude is None:
        return None

    cache_key = f"reverse-geocode:{float(latitude):.6f},{float(longitude):.6f}"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    query = urllib.parse.urlencode(
        {
            'lat': f'{float(latitude):.6f}',
            'lon': f'{float(longitude):.6f}',
            'format': 'jsonv2',
            'addressdetails': 1,
            'zoom': 16,
        }
    )
    url = f'https://nominatim.openstreetmap.org/reverse?{query}'

    try:
        request = urllib.request.Request(
            url,
            headers={
                'User-Agent': 'foodtruck-bi/1.0 (+local dashboard)',
                'Accept': 'application/json',
            },
        )
        with urllib.request.urlopen(request, timeout=5.0) as response:
            payload = json.loads(response.read().decode('utf-8'))

        address = payload.get('address') or {}
        road = address.get('road') or address.get('pedestrian') or address.get('footway') or address.get('residential')
        house_number = address.get('house_number')
        postcode = address.get('postcode')
        city = (
            address.get('city')
            or address.get('town')
            or address.get('village')
            or address.get('municipality')
            or address.get('hamlet')
        )

        first_line = ' '.join(part for part in [house_number, road] if part)
        second_line = ' '.join(part for part in [postcode, city] if part)
        location_text = ', '.join(part for part in [first_line, second_line] if part)
        if not location_text:
            location_text = payload.get('display_name', '').split(',')[0].strip() or None

        cache.set(cache_key, location_text, timeout=60 * 60 * 24 * 30)
        return location_text
    except Exception:
        # Keep API resilient even if reverse geocoding is unavailable.
        # Do not cache failures for long: retry on next requests.
        return None


def _haversine_distance_km(lat1, lng1, lat2, lng2):
    """Compute great-circle distance between two points in kilometers."""
    import math

    dlat = math.radians(float(lat2) - float(lat1))
    dlng = math.radians(float(lng2) - float(lng1))
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(float(lat1)))
        * math.cos(math.radians(float(lat2)))
        * math.sin(dlng / 2) ** 2
    )
    return 6371 * 2 * math.asin(math.sqrt(a))


def _resolve_date_range(request):
    today = timezone.localdate()
    range_key = request.GET.get('range', '7d')

    if range_key == 'today':
        return today, today, range_key
    if range_key == '30d':
        return today - timedelta(days=29), today, range_key

    if range_key == 'custom':
        start_date = _parse_iso_date(request.GET.get('start_date'))
        end_date = _parse_iso_date(request.GET.get('end_date'))
        if start_date and end_date and start_date <= end_date:
            return start_date, end_date, range_key

    return today - timedelta(days=6), today, '7d'


class FoodTruckOwnerDashboardMixin(LoginRequiredMixin):
    """Shared ownership guard and dashboard helpers."""

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        self.foodtruck = get_object_or_404(
            FoodTruck.objects.select_related('subscription__plan'),
            slug=kwargs.get('slug'),
            owner=request.user,
            is_active=True,
        )
        return super().dispatch(request, *args, **kwargs)

    def get_dashboard_service(self):
        return DashboardService(self.foodtruck)

    def get_date_window(self):
        return _resolve_date_range(self.request)


def _decimal_as_float(value):
    return float(value) if value is not None else 0.0


def _serialize_order(order, display_mode=FoodTruck.PriceDisplayMode.TAX_INCLUDED):
    amount = order.total_amount or 0
    if display_mode == FoodTruck.PriceDisplayMode.TAX_EXCLUDED:
        amount = amount - (order.tax_amount or 0)
    return {
        'id': order.id,
        'status': order.status,
        'total_amount': _decimal_as_float(amount),
        'paid_at': order.paid_at.isoformat() if order.paid_at else None,
        'pickup_time': order.pickup_slot.start_time.isoformat() if order.pickup_slot else None,
        'customer_name': order.customer_name,
        'items_count': order.items.count(),
    }


class FoodTruckDashboardView(FoodTruckOwnerDashboardMixin, TemplateView):
    template_name = 'foodtrucks/dashboard.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        start_date, end_date, active_range = self.get_date_window()
        service = self.get_dashboard_service()
        initial_kpis = service.get_kpis(start_date, end_date)

        context.update(
            {
                'foodtruck': self.foodtruck,
                'categories': _load_menu_categories(self.foodtruck),
                'price_display_mode': self.foodtruck.price_display_mode,
                'initial_kpis': {
                    'total_orders': initial_kpis['total_orders'],
                    'total_revenue': _decimal_as_float(initial_kpis['total_revenue']),
                    'average_order_value': _decimal_as_float(initial_kpis['average_order_value']),
                    'completion_rate': _decimal_as_float(initial_kpis['completion_rate']),
                    'options_revenue_pct': _decimal_as_float(initial_kpis['options_revenue_pct']),
                },
                'active_range': active_range,
                'start_date': start_date.isoformat(),
                'end_date': end_date.isoformat(),
            }
        )
        return context


class FoodTruckBusinessIntelligenceView(FoodTruckOwnerDashboardMixin, TemplateView):
    template_name = 'foodtrucks/business_intelligence.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(
            {
                'foodtruck': self.foodtruck,
                'categories': _load_menu_categories(self.foodtruck),
            }
        )
        return context


class FoodTruckBIEventsView(FoodTruckOwnerDashboardMixin, TemplateView):
    template_name = 'foodtrucks/bi_events.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(
            {
                'foodtruck': self.foodtruck,
                'categories': _load_menu_categories(self.foodtruck),
            }
        )
        return context


class FoodTruckBIPricingView(FoodTruckOwnerDashboardMixin, TemplateView):
    template_name = 'foodtrucks/bi_pricing.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(
            {
                'foodtruck': self.foodtruck,
                'categories': _load_menu_categories(self.foodtruck),
            }
        )
        return context


class FoodTruckOptionsAnalysisView(FoodTruckOwnerDashboardMixin, TemplateView):
    template_name = 'foodtrucks/options_analysis.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        start_date, end_date, active_range = self.get_date_window()
        context.update(
            {
                'foodtruck': self.foodtruck,
                'categories': _load_menu_categories(self.foodtruck),
                'active_range': active_range,
                'start_date': start_date.isoformat(),
                'end_date': end_date.isoformat(),
                'price_display_mode': self.foodtruck.price_display_mode,
            }
        )
        return context


class DashboardKpiAPIView(FoodTruckOwnerDashboardMixin, View):
    def get(self, request, *args, **kwargs):
        start_date, end_date, active_range = self.get_date_window()
        category_id = _parse_category_id(request)
        display_mode = _parse_display_mode(request, self.foodtruck)
        kpis = self.get_dashboard_service().get_kpis(
            start_date,
            end_date,
            category_id=category_id,
            display_mode=display_mode,
        )
        return JsonResponse(
            {
                'range': active_range,
                'display_mode': display_mode,
                'start_date': start_date.isoformat(),
                'end_date': end_date.isoformat(),
                'data': {
                    'total_orders': kpis['total_orders'],
                    'total_revenue': _decimal_as_float(kpis['total_revenue']),
                    'average_order_value': _decimal_as_float(kpis['average_order_value']),
                    'completion_rate': _decimal_as_float(kpis['completion_rate']),
                    'options_revenue_pct': _decimal_as_float(kpis['options_revenue_pct']),
                },
            }
        )


class DashboardRevenueAPIView(FoodTruckOwnerDashboardMixin, View):
    def get(self, request, *args, **kwargs):
        start_date, end_date, active_range = self.get_date_window()
        interval = request.GET.get('interval', 'day')
        category_id = _parse_category_id(request)
        display_mode = _parse_display_mode(request, self.foodtruck)
        points = self.get_dashboard_service().get_revenue_timeseries(
            start_date,
            end_date,
            interval=interval,
            category_id=category_id,
            display_mode=display_mode,
        )

        return JsonResponse(
            {
                'range': active_range,
                'interval': interval,
                'display_mode': display_mode,
                'start_date': start_date.isoformat(),
                'end_date': end_date.isoformat(),
                'data': [
                    {
                        'date': point['date'],
                        'revenue': _decimal_as_float(point['revenue']),
                    }
                    for point in points
                ],
            }
        )


class DashboardOrdersAPIView(FoodTruckOwnerDashboardMixin, View):
    def get(self, request, *args, **kwargs):
        start_date, end_date, active_range = self.get_date_window()
        category_id = _parse_category_id(request)
        display_mode = _parse_display_mode(request, self.foodtruck)
        try:
            limit = int(request.GET.get('limit', '20'))
        except ValueError:
            limit = 20
        limit = max(1, min(limit, 100))

        orders = self.get_dashboard_service().get_recent_orders(
            limit=limit,
            start_date=start_date,
            end_date=end_date,
            category_id=category_id,
        )
        return JsonResponse(
            {
                'range': active_range,
                'display_mode': display_mode,
                'start_date': start_date.isoformat(),
                'end_date': end_date.isoformat(),
                'data': [_serialize_order(order, display_mode=display_mode) for order in orders],
            }
        )


class DashboardMenuPerformanceAPIView(FoodTruckOwnerDashboardMixin, View):
    def get(self, request, *args, **kwargs):
        start_date, end_date, active_range = self.get_date_window()
        category_id = _parse_category_id(request)
        display_mode = _parse_display_mode(request, self.foodtruck)
        try:
            limit = int(request.GET.get('limit', '10'))
        except ValueError:
            limit = 10
        limit = max(1, min(limit, 50))

        top_items = self.get_dashboard_service().get_top_items(
            limit=limit,
            start_date=start_date,
            end_date=end_date,
            category_id=category_id,
            display_mode=display_mode,
        )
        return JsonResponse(
            {
                'range': active_range,
                'display_mode': display_mode,
                'start_date': start_date.isoformat(),
                'end_date': end_date.isoformat(),
                'data': [
                    {
                        'item_name': row['product_name'],
                        'quantity_sold': row['quantity_sold'],
                        'revenue_generated': _decimal_as_float(row['revenue_generated']),
                    }
                    for row in top_items
                ],
            }
        )


class DashboardMenuCategoryPerformanceAPIView(FoodTruckOwnerDashboardMixin, View):
    def get(self, request, *args, **kwargs):
        start_date, end_date, active_range = self.get_date_window()
        category_id = _parse_category_id(request)
        display_mode = _parse_display_mode(request, self.foodtruck)
        try:
            limit = int(request.GET.get('limit', '8'))
        except ValueError:
            limit = 8
        limit = max(1, min(limit, 20))

        rows = self.get_dashboard_service().get_category_performance(
            start_date=start_date,
            end_date=end_date,
            limit=limit,
            category_id=category_id,
            display_mode=display_mode,
        )
        return JsonResponse(
            {
                'range': active_range,
                'display_mode': display_mode,
                'start_date': start_date.isoformat(),
                'end_date': end_date.isoformat(),
                'data': [
                    {
                        'category_name': row['category_name'],
                        'quantity_sold': row['quantity_sold'],
                        'revenue_generated': _decimal_as_float(row['revenue_generated']),
                    }
                    for row in rows
                ],
            }
        )


class DashboardSlotPerformanceAPIView(FoodTruckOwnerDashboardMixin, View):
    def get(self, request, *args, **kwargs):
        start_date, end_date, active_range = self.get_date_window()
        category_id = _parse_category_id(request)
        slots = self.get_dashboard_service().get_slot_performance(start_date=start_date, end_date=end_date, category_id=category_id)

        return JsonResponse(
            {
                'range': active_range,
                'start_date': start_date.isoformat(),
                'end_date': end_date.isoformat(),
                'data': [
                    {
                        'slot': slot['slot'],
                        'start_time': slot['start_time'].isoformat(),
                        'end_time': slot['end_time'].isoformat(),
                        'orders_count': slot['orders_count'],
                        'capacity': slot['capacity'],
                        'capacity_usage': _decimal_as_float(slot['capacity_usage']),
                    }
                    for slot in slots
                ],
            }
        )


class DashboardSlotUtilizationAPIView(FoodTruckOwnerDashboardMixin, View):
    def get(self, request, *args, **kwargs):
        start_date, end_date, active_range = self.get_date_window()
        category_id = _parse_category_id(request)
        rows = self.get_dashboard_service().get_slot_utilization(start_date, end_date, category_id=category_id)

        return JsonResponse(
            {
                'range': active_range,
                'start_date': start_date.isoformat(),
                'end_date': end_date.isoformat(),
                'data': [
                    {
                        'slot_id': row['slot_id'],
                        'slot': row['slot'],
                        'start_time': row['start_time'].isoformat(),
                        'end_time': row['end_time'].isoformat(),
                        'total_orders': row['total_orders'],
                        'capacity': row['capacity'],
                        'utilization_rate': _decimal_as_float(row['utilization_rate']),
                        'utilization_pct': _decimal_as_float(row['utilization_pct']),
                    }
                    for row in rows
                ],
            }
        )


class DashboardSlotRevenueAPIView(FoodTruckOwnerDashboardMixin, View):
    def get(self, request, *args, **kwargs):
        start_date, end_date, active_range = self.get_date_window()
        category_id = _parse_category_id(request)
        display_mode = _parse_display_mode(request, self.foodtruck)
        rows = self.get_dashboard_service().get_revenue_per_slot(
            start_date,
            end_date,
            category_id=category_id,
            display_mode=display_mode,
        )

        return JsonResponse(
            {
                'range': active_range,
                'display_mode': display_mode,
                'start_date': start_date.isoformat(),
                'end_date': end_date.isoformat(),
                'data': [
                    {
                        'slot_id': row['slot_id'],
                        'slot': row['slot'],
                        'start_time': row['start_time'].isoformat(),
                        'end_time': row['end_time'].isoformat(),
                        'total_orders': row['total_orders'],
                        'total_revenue': _decimal_as_float(row['total_revenue']),
                        'avg_order_value': _decimal_as_float(row['avg_order_value']),
                    }
                    for row in rows
                ],
            }
        )


class DashboardSlotHourlyAPIView(FoodTruckOwnerDashboardMixin, View):
    def get(self, request, *args, **kwargs):
        start_date, end_date, active_range = self.get_date_window()
        category_id = _parse_category_id(request)
        display_mode = _parse_display_mode(request, self.foodtruck)
        rows = self.get_dashboard_service().get_hourly_performance(
            start_date,
            end_date,
            category_id=category_id,
            display_mode=display_mode,
        )

        return JsonResponse(
            {
                'range': active_range,
                'display_mode': display_mode,
                'start_date': start_date.isoformat(),
                'end_date': end_date.isoformat(),
                'data': [
                    {
                        'hour': row['hour'],
                        'orders': row['orders'],
                        'revenue': _decimal_as_float(row['revenue']),
                        'avg_order_value': _decimal_as_float(row['avg_order_value']),
                    }
                    for row in rows
                ],
            }
        )


class DashboardSlotHeatmapAPIView(FoodTruckOwnerDashboardMixin, View):
    def get(self, request, *args, **kwargs):
        start_date, end_date, active_range = self.get_date_window()
        category_id = _parse_category_id(request)
        rows = self.get_dashboard_service().get_slot_heatmap(start_date, end_date, category_id=category_id)

        return JsonResponse(
            {
                'range': active_range,
                'start_date': start_date.isoformat(),
                'end_date': end_date.isoformat(),
                'data': [
                    {
                        'weekday': row['weekday'],
                        'hour': row['hour'],
                        'orders': row['orders'],
                    }
                    for row in rows
                ],
            }
        )


class DashboardSlotInsightsAPIView(FoodTruckOwnerDashboardMixin, View):
    def get(self, request, *args, **kwargs):
        category_id = _parse_category_id(request)
        payload = self.get_dashboard_service().get_slot_insights(category_id=category_id)

        return JsonResponse(
            {
                'data': {
                    'underperforming_slots': [
                        {
                            'slot_id': row['slot_id'],
                            'slot': row['slot'],
                            'start_time': row['start_time'].isoformat(),
                            'total_orders': row['total_orders'],
                            'capacity': row['capacity'],
                            'utilization_pct': _decimal_as_float(row['utilization_pct']),
                        }
                        for row in payload['underperforming_slots']
                    ],
                    'optimal_slots': [
                        {
                            'slot_id': row['slot_id'],
                            'slot': row['slot'],
                            'start_time': row['start_time'].isoformat(),
                            'total_orders': row['total_orders'],
                            'capacity': row['capacity'],
                            'utilization_pct': _decimal_as_float(row['utilization_pct']),
                        }
                        for row in payload['optimal_slots']
                    ],
                    'saturated_slots': [
                        {
                            'slot_id': row['slot_id'],
                            'slot': row['slot'],
                            'start_time': row['start_time'].isoformat(),
                            'total_orders': row['total_orders'],
                            'capacity': row['capacity'],
                            'utilization_pct': _decimal_as_float(row['utilization_pct']),
                        }
                        for row in payload['saturated_slots']
                    ],
                }
            }
        )


class DashboardOptionPerformanceAPIView(FoodTruckOwnerDashboardMixin, View):
    def get(self, request, *args, **kwargs):
        start_date, end_date, active_range = self.get_date_window()
        category_id = _parse_category_id(request)
        try:
            limit = int(request.GET.get('limit', '10'))
        except ValueError:
            limit = 10
        limit = max(1, min(limit, 30))

        payload = self.get_dashboard_service().get_option_performance(
            start_date=start_date,
            end_date=end_date,
            limit=limit,
            category_id=category_id,
        )
        return JsonResponse(
            {
                'range': active_range,
                'start_date': start_date.isoformat(),
                'end_date': end_date.isoformat(),
                'data': {
                    'top_options': [
                        {
                            'option_name': row['option__name'],
                            'selection_count': row['selection_count'],
                            'total_revenue': _decimal_as_float(row['total_revenue']),
                        }
                        for row in payload['top_options']
                    ],
                    'top_paying_options': [
                        {
                            'option_name': row['option__name'],
                            'selection_count': row['selection_count'],
                            'total_revenue': _decimal_as_float(row['total_revenue']),
                        }
                        for row in payload['top_paying_options']
                    ],
                    'orders_with_options': payload['orders_with_options'],
                    'orders_with_options_pct': _decimal_as_float(payload['orders_with_options_pct']),
                    'total_option_revenue': _decimal_as_float(payload['total_option_revenue']),
                    'avg_option_revenue_per_order': _decimal_as_float(payload['avg_option_revenue_per_order']),
                },
            }
        )


class DashboardSlotRecommendationsAPIView(FoodTruckOwnerDashboardMixin, View):
    def get(self, request, *args, **kwargs):
        category_id = _parse_category_id(request)
        payload = self.get_dashboard_service().get_slot_recommendations(category_id=category_id)

        return JsonResponse(
            {
                'data': {
                    'increase_capacity_slots': [
                        {
                            'slot_id': row['slot_id'],
                            'slot': row['slot'],
                            'start_time': row['start_time'].isoformat(),
                            'utilization_pct': _decimal_as_float(row['utilization_pct']),
                        }
                        for row in payload['increase_capacity_slots']
                    ],
                    'reduce_capacity_slots': [
                        {
                            'slot_id': row['slot_id'],
                            'slot': row['slot'],
                            'start_time': row['start_time'].isoformat(),
                            'utilization_pct': _decimal_as_float(row['utilization_pct']),
                        }
                        for row in payload['reduce_capacity_slots']
                    ],
                    'suggested_new_slots': payload['suggested_new_slots'],
                }
            }
        )


class DashboardBusinessIntelligenceAPIView(FoodTruckOwnerDashboardMixin, View):
    def get(self, request, *args, **kwargs):
        today = timezone.localdate()
        prediction_date = today + timedelta(days=1)

        try:
            horizon_days = int(request.GET.get('horizon_days', '14'))
        except ValueError:
            horizon_days = 14
        horizon_days = max(1, min(horizon_days, 90))

        try:
            min_attendance = int(request.GET.get('min_attendance', '0'))
        except ValueError:
            min_attendance = 0
        min_attendance = max(0, min_attendance)

        try:
            min_score = float(request.GET.get('min_score', '0'))
        except ValueError:
            min_score = 0.0
        min_score = max(0.0, min(min_score, 100.0))

        try:
            event_limit = int(request.GET.get('limit', '5'))
        except ValueError:
            event_limit = 5
        event_limit = max(1, min(event_limit, 20))

        keyword = (request.GET.get('keyword') or '').strip()
        keywords_raw = (request.GET.get('keywords') or '').strip()
        selected_keywords = [value.strip() for value in keywords_raw.split(',') if value.strip()]

        def _normalize_keyword(value):
            lowered = (value or '').strip().lower()
            normalized = unicodedata.normalize('NFD', lowered)
            return ''.join(char for char in normalized if unicodedata.category(char) != 'Mn')

        keyword_aliases = {
            'festival': {'festival', 'fest', 'fete', 'fete de rue', 'fete locale', 'fair'},
            'market': {'market', 'marche', 'marche local', 'bazaar'},
            'concert': {'concert', 'live', 'music', 'musique', 'show'},
            'sports': {'sport', 'sports', 'match', 'tournoi', 'game'},
            'family': {'family', 'famille', 'kids', 'enfant', 'children'},
        }
        reverse_alias = {}
        for canonical, aliases in keyword_aliases.items():
            for alias in aliases:
                reverse_alias[_normalize_keyword(alias)] = canonical

        expanded_keywords = []
        seen_keywords = set()
        for raw_keyword in selected_keywords:
            normalized_raw = _normalize_keyword(raw_keyword)
            if not normalized_raw:
                continue

            canonical = reverse_alias.get(normalized_raw)
            candidates = {raw_keyword, normalized_raw}
            if canonical:
                candidates.update(keyword_aliases[canonical])

            for candidate in candidates:
                normalized_candidate = _normalize_keyword(candidate)
                if normalized_candidate and normalized_candidate not in seen_keywords:
                    seen_keywords.add(normalized_candidate)
                    expanded_keywords.append(candidate)
        period = (request.GET.get('period') or 'full_day').strip()
        allowed_periods = {'morning', 'noon', 'evening', 'full_day'}
        if period not in allowed_periods:
            period = 'full_day'

        try:
            radius_km = float(request.GET.get('radius_km', '0'))
        except ValueError:
            radius_km = 0.0
        radius_km = max(0.0, min(radius_km, 500.0))

        location_service = LocationAIService(self.foodtruck)
        pricing_service = PricingAIService()
        event_service = EventAIService()
        revenue_service = RevenuePredictionService()

        best_spots = location_service.find_best_spots(self.foodtruck)

        active_items = list(
            self.foodtruck.menus.filter(is_active=True)
            .values_list('categories__items__id', flat=True)
        )
        item_ids = [item_id for item_id in active_items if item_id is not None]
        from menu.models import Item
        pricing_payload = []
        if item_ids:
            items = Item.objects.filter(id__in=item_ids).select_related('category').order_by('display_order', 'name')[:5]
            for item in items:
                suggestion = pricing_service.suggest_price(item)
                pricing_payload.append({
                    'item_id': item.id,
                    'item_name': item.name,
                    'current_price': float(suggestion['current_price']),
                    'suggested_price': float(suggestion['suggested_price']),
                    'confidence_score': suggestion['confidence_score'],
                    'reason': suggestion['reason'],
                })

        import math
        total_events_in_db = Event.objects.count()
        filter_trace = []

        base_qs = Event.objects.filter(
            start_date__lte=today + timedelta(days=horizon_days),
            end_date__gte=today,
        )
        count_after_horizon = base_qs.count()
        filter_trace.append({
            'step': 'horizon',
            'label': str(_('Within {horizon_days}-day horizon')).format(horizon_days=horizon_days),
            'count': count_after_horizon,
        })

        upcoming_events = base_qs

        if radius_km > 0 and self.foodtruck.latitude and self.foodtruck.longitude:
            ft_lat = float(self.foodtruck.latitude)
            ft_lng = float(self.foodtruck.longitude)
            lat_delta = radius_km / 111.0
            lng_delta = radius_km / (111.0 * math.cos(math.radians(ft_lat)))
            upcoming_events = upcoming_events.filter(
                latitude__gte=ft_lat - lat_delta,
                latitude__lte=ft_lat + lat_delta,
                longitude__gte=ft_lng - lng_delta,
                longitude__lte=ft_lng + lng_delta,
            )
            count_after_bbox = upcoming_events.count()
            # Precise haversine filter on the bounding-box result set
            bbox_ids = list(upcoming_events.values_list('id', 'latitude', 'longitude'))
            precise_ids = []
            for eid, elat, elng in bbox_ids:
                dlat = math.radians(float(elat) - ft_lat)
                dlng = math.radians(float(elng) - ft_lng)
                a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(ft_lat)) * math.cos(math.radians(float(elat))) * math.sin(dlng / 2) ** 2
                dist_km = 6371 * 2 * math.asin(math.sqrt(a))
                if dist_km <= radius_km:
                    precise_ids.append(eid)
            upcoming_events = upcoming_events.filter(id__in=precise_ids)
            count_after_radius = upcoming_events.count()
            filter_trace.append({
                'step': 'radius',
                'label': str(_('Within {radius_km} km radius')).format(radius_km=f'{radius_km:.0f}'),
                'count': count_after_radius,
            })
        if min_attendance > 0:
            upcoming_events = upcoming_events.filter(expected_attendance__gte=min_attendance)
            count_after_attendance = upcoming_events.count()
            filter_trace.append({
                'step': 'attendance',
                'label': f'Min attendance ≥ {min_attendance}',
                'count': count_after_attendance,
            })

        if keyword:
            upcoming_events = upcoming_events.filter(name__icontains=keyword)
            count_after_keyword = upcoming_events.count()
            filter_trace.append({
                'step': 'keyword',
                'label': f'Keyword "{keyword}"',
                'count': count_after_keyword,
            })

        if selected_keywords:
            keyword_query = Q()
            for selected in expanded_keywords:
                keyword_query |= Q(name__icontains=selected)
            upcoming_events = upcoming_events.filter(keyword_query)
            count_after_keywords = upcoming_events.count()
            filter_trace.append({
                'step': 'keywords',
                'label': str(_('Keywords: {selected_keywords}')).format(selected_keywords=', '.join(selected_keywords)),
                'count': count_after_keywords,
            })

        period_tokens = {
            'morning': ['morning', 'breakfast', 'brunch', 'matin', 'petit dejeuner'],
            'noon': ['noon', 'lunch', 'midi', 'dejeuner'],
            'evening': ['evening', 'night', 'dinner', 'soir', 'afterwork'],
        }
        if period in period_tokens:
            period_query = Q()
            for token in period_tokens[period]:
                period_query |= Q(name__icontains=token)
            upcoming_events = upcoming_events.filter(period_query)
            count_after_period = upcoming_events.count()
            filter_trace.append({
                'step': 'period',
                'label': f'Time slot: {period}',
                'count': count_after_period,
            })

        upcoming_events = list(upcoming_events.order_by('start_date')[:50])
        analyzed_events_count = len(upcoming_events)

        _feature_extractor = EventFeatureExtractor()
        _scorer = EventScoringService()

        # Pre-fetch all existing AI analyses for the candidate events in one query.
        ai_analyses = {
            a.event_id: a
            for a in EventAIAnalysis.objects.filter(
                event__in=upcoming_events,
                prompt_version=CURRENT_PROMPT_VERSION,
            )
        }
        logger.debug(
            f"BI API: found {len(ai_analyses)} AI analyses for {len(upcoming_events)} events (v{CURRENT_PROMPT_VERSION})"
        )

        event_payload = []
        score_filtered_count = 0
        for event in upcoming_events:
            ai_analysis = ai_analyses.get(event.id)
            ai_analyzed = ai_analysis is not None
            
            # Variables for explanation (only set if AI-analyzed)
            scoring_explanation = None

            if ai_analyzed:
                # Rich deterministic score built from persisted AI signals.
                try:
                    signals = validate_and_normalize(ai_analysis.normalized_data)
                    features = _feature_extractor.extract(event)
                    scoring_result = _scorer.score(features, signals)
                    opportunity_score = float(scoring_result.final_score)
                    breakdown = scoring_result.breakdown.to_dict()
                    breakdown['source'] = 'ai_analysis'
                    scoring_explanation = explain_score(
                        scoring_result, signals, features, language=request.LANGUAGE_CODE
                    )
                    # Predicted revenue: reuse legacy service (own logic, unrelated to AI signals).
                    legacy_result = event_service.evaluate_event(self.foodtruck, event)
                    predicted_revenue = float(legacy_result['predicted_revenue'])
                except Exception as e:
                    # Defensive: fall back silently if normalisation fails.
                    logger.warning(f"Failed to use AI analysis for event {event.id}: {e}")
                    ai_analyzed = False

            if not ai_analyzed:
                # Legacy score — enqueue background analysis for next request.
                legacy_result = event_service.evaluate_event(self.foodtruck, event)
                opportunity_score = legacy_result['opportunity_score']
                predicted_revenue = float(legacy_result['predicted_revenue'])
                breakdown = legacy_result['breakdown']
                breakdown['source'] = 'legacy'
                try:
                    analyze_event_task.delay(event.id)
                    logger.debug(f"Enqueued AI analysis task for event {event.id}")
                except Exception as exc:
                    logger.error(f"Failed to enqueue AI analysis for event {event.id}: {exc}")

            if opportunity_score < min_score:
                score_filtered_count += 1
                continue

            location_text = (event.location_text or '').strip() or _reverse_geocode_location(event.latitude, event.longitude)
            distance_km = None
            if (
                self.foodtruck.latitude is not None
                and self.foodtruck.longitude is not None
                and event.latitude is not None
                and event.longitude is not None
            ):
                try:
                    distance_km = _haversine_distance_km(
                        self.foodtruck.latitude,
                        self.foodtruck.longitude,
                        event.latitude,
                        event.longitude,
                    )
                except Exception:
                    distance_km = None
            
            # Translate location label based on language
            if request.LANGUAGE_CODE == 'fr':
                location_label = "Lieu de l'événement"
            else:
                location_label = "Event Location"

            event_entry = {
                'event_id': event.id,
                'event_name': event.name,
                'description': event.description or None,
                'image_url': event.image_url or None,
                'source_url': event.source_url or None,
                'category': event.category or None,
                'start_date': event.start_date.isoformat(),
                'end_date': event.end_date.isoformat(),
                'location_label': location_label,
                'location_text': location_text,
                'latitude': float(event.latitude),
                'longitude': float(event.longitude),
                'distance_km': distance_km,
                'expected_attendance': event.expected_attendance,
                'ai_analyzed': ai_analyzed,
                'opportunity_score': opportunity_score,
                'predicted_revenue': predicted_revenue,
                'breakdown': breakdown,
            }
            
            # Add scoring explanation if available
            if scoring_explanation:
                event_entry['scoring_explanation'] = scoring_explanation
            
            event_payload.append(event_entry)

        if min_score > 0:
            filter_trace.append({
                'step': 'min_score',
                'label': f'Min score ≥ {min_score}',
                'count': analyzed_events_count - score_filtered_count,
            })

        event_payload = sorted(
            event_payload,
            key=lambda item: (item['opportunity_score'], item['predicted_revenue']),
            reverse=True,
        )[:event_limit]
        event_payload = sorted(
            event_payload,
            key=lambda item: (item['start_date'], -item['opportunity_score'], -item['predicted_revenue']),
        )
        retained_events_count = len(event_payload)

        empty_reasons = []
        if retained_events_count == 0:
            if total_events_in_db == 0:
                empty_reasons.append('The events database is empty. Add events via the admin before using opportunity search.')
            elif analyzed_events_count == 0 and count_after_horizon == 0:
                empty_reasons.append(f'No event exists for the next {horizon_days} days ({total_events_in_db} total in database). Try extending the horizon.')
            elif analyzed_events_count == 0:
                empty_reasons.append('All events in this horizon were filtered out. See details below.')
            if radius_km > 0:
                empty_reasons.append(f'Try increasing the search radius (currently {radius_km:.0f} km) or set it to 0 to ignore distance.')
            if min_attendance > 0:
                empty_reasons.append(f'Try lowering minimum attendance (currently {min_attendance}).')
            if min_score > 0:
                empty_reasons.append(f'Try lowering minimum score (currently {min_score}).')
            if period != 'full_day':
                empty_reasons.append(f'No event name matches the "{period}" time slot tokens. Try "Full day".')
            if selected_keywords or keyword:
                empty_reasons.append('Try removing or broadening selected keywords.')

        revenue_result = revenue_service.predict_day(self.foodtruck, prediction_date)

        return JsonResponse(
            {
                'date': prediction_date.isoformat(),
                'filters': {
                    'horizon_days': horizon_days,
                    'min_attendance': min_attendance,
                    'min_score': min_score,
                    'keyword': keyword,
                    'keywords': selected_keywords,
                    'period': period,
                    'limit': event_limit,
                    'radius_km': radius_km,
                },
                'search_feedback': {
                    'total_events_in_db': total_events_in_db,
                    'analyzed_events_count': analyzed_events_count,
                    'retained_events_count': retained_events_count,
                    'empty_reasons': empty_reasons,
                    'filter_trace': filter_trace,
                },
                'data': {
                    'best_spots': best_spots,
                    'pricing_suggestions': pricing_payload,
                    'event_opportunities': event_payload,
                    'revenue_prediction': {
                        'predicted_revenue': float(revenue_result['predicted_revenue']),
                        'confidence_score': revenue_result['confidence_score'],
                        'breakdown': revenue_result['breakdown'],
                    },
                },
            }
        )
