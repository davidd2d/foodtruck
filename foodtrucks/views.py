from datetime import date, timedelta

from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, render
from django.views.generic import TemplateView, View
from django.utils import timezone

from .models import FoodTruck
from analytics.services import DashboardService
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
    try:
        menu = MenuService.get_active_menu_for_foodtruck(foodtruck.slug)
        categories = menu.categories.order_by('display_order', 'name')
    except Http404:
        categories = []

    available_slots = []
    default_slot_id = None
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
                },
                'active_range': active_range,
                'start_date': start_date.isoformat(),
                'end_date': end_date.isoformat(),
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
