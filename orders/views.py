from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Count, Sum
from django.http import Http404, HttpResponseRedirect
from django.shortcuts import render, get_object_or_404
from django.urls import reverse, reverse_lazy
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy as _lazy
from django.views.generic import ListView, CreateView, UpdateView, DeleteView
from django.views.generic import TemplateView

from foodtrucks.models import FoodTruck
from .forms import LocationForm
from .models import Location, Order, Ticket
from menu.services.menu_service import MenuService
from orders.services.order_service import OrderService

DAY_NAMES = [
    (_lazy("Monday"), 0),
    (_lazy("Tuesday"), 1),
    (_lazy("Wednesday"), 2),
    (_lazy("Thursday"), 3),
    (_lazy("Friday"), 4),
    (_lazy("Saturday"), 5),
    (_lazy("Sunday"), 6),
]


@login_required
def history(request):
    return render(request, 'orders/history.html')


@login_required
def manage_pickup_slots(request, slug):
    """
    Render the management UI for pickup slots for a specific food truck.
    """
    foodtruck = get_object_or_404(
        FoodTruck,
        slug=slug,
        owner=request.user,
    )
    return render(request, 'orders/slot_management.html', {
        'foodtruck': foodtruck,
    })


@login_required
def working_hours(request, slug):
    foodtruck = get_object_or_404(
        FoodTruck.objects.prefetch_related('supported_preferences'),
        slug=slug,
        owner=request.user,
        is_active=True,
    )
    categories = _load_menu_categories(foodtruck)
    location_qs = Location.objects.filter(food_truck=foodtruck, is_active=True).order_by('name', 'city')
    base_label = _format_base_location(foodtruck)
    location_choices = [
        {
            'id': None,
            'label': base_label,
        }
    ]
    for location in location_qs:
        location_choices.append({
            'id': location.id,
            'label': location.name if location.name else location.get_full_address(),
            'city': location.city,
            'postal_code': location.postal_code,
        })
    return render(request, 'orders/working_hours/index.html', {
        'day_names': DAY_NAMES,
        'foodtruck': foodtruck,
        'categories': categories,
        'location_choices': location_choices,
        'base_location_label': base_label,
    })


class FoodTruckOwnerMixin(LoginRequiredMixin):
    def dispatch(self, request, *args, **kwargs):
        slug = self.kwargs.get('slug')
        self.foodtruck = FoodTruck.objects.filter(slug=slug, owner=request.user, is_active=True).first()
        if not self.foodtruck:
            raise Http404
        return super().dispatch(request, *args, **kwargs)

    def get_menu_categories(self):
        return _load_menu_categories(self.foodtruck)


class FoodTruckContextMixin(LoginRequiredMixin):
    def dispatch(self, request, *args, **kwargs):
        slug = self.kwargs.get('slug')
        self.foodtruck = FoodTruck.objects.filter(slug=slug, is_active=True).first()
        if not self.foodtruck:
            raise Http404
        return super().dispatch(request, *args, **kwargs)

    def get_menu_categories(self):
        return _load_menu_categories(self.foodtruck)


class OrderDashboardView(FoodTruckOwnerMixin, TemplateView):
    """Render the owner order dashboard shell with an initial server-side snapshot."""

    template_name = 'orders/dashboard.html'

    SECTION_CONFIG = (
        (Order.Status.PENDING, _lazy('Pending'), 'warning'),
        (Order.Status.CONFIRMED, _lazy('Confirmed'), 'primary'),
        (Order.Status.PREPARING, _lazy('Preparing'), 'info'),
        (Order.Status.READY, _lazy('Ready'), 'success'),
        (Order.Status.COMPLETED, _lazy('Completed'), 'secondary'),
    )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        orders = list(OrderService.get_dashboard_orders(self.foodtruck, {}))
        grouped_orders = {status: [] for status, _, _ in self.SECTION_CONFIG}
        for order in orders:
            grouped_orders.setdefault(order.status, []).append(order)

        context.update({
            'foodtruck': self.foodtruck,
            'categories': self.get_menu_categories(),
            'dashboard_sections': [
                {
                    'key': status,
                    'label': label,
                    'badge': badge,
                    'orders': grouped_orders.get(status, []),
                }
                for status, label, badge in self.SECTION_CONFIG
            ],
        })
        return context


class LocationListView(FoodTruckOwnerMixin, ListView):
    model = Location
    template_name = 'orders/locations/list.html'
    context_object_name = 'locations'

    def get_queryset(self):
        return Location.objects.filter(food_truck=self.foodtruck, is_active=True).select_related('food_truck')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            'foodtruck': self.foodtruck,
            'base_coordinates': self.foodtruck.get_base_coordinates(),
            'categories': self.get_menu_categories(),
        })
        return context


class LocationCreateView(FoodTruckOwnerMixin, CreateView):
    model = Location
    form_class = LocationForm
    template_name = 'orders/locations/form.html'

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['food_truck'] = self.foodtruck
        return kwargs

    def form_valid(self, form):
        form.instance.food_truck = self.foodtruck
        messages.success(self.request, 'Location saved successfully.')
        return super().form_valid(form)

    def get_success_url(self):
        return reverse_lazy('orders:location-list', kwargs={'slug': self.foodtruck.slug})

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['foodtruck'] = self.foodtruck
        context['categories'] = self.get_menu_categories()
        return context


class LocationUpdateView(FoodTruckOwnerMixin, UpdateView):
    model = Location
    form_class = LocationForm
    template_name = 'orders/locations/form.html'

    def get_queryset(self):
        return Location.objects.filter(food_truck=self.foodtruck)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['food_truck'] = self.foodtruck
        return kwargs

    def form_valid(self, form):
        messages.success(self.request, 'Location updated successfully.')
        return super().form_valid(form)

    def get_success_url(self):
        return reverse_lazy('orders:location-list', kwargs={'slug': self.foodtruck.slug})

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['foodtruck'] = self.foodtruck
        context['categories'] = self.get_menu_categories()
        return context


class LocationDeleteView(FoodTruckOwnerMixin, DeleteView):
    model = Location
    template_name = 'orders/locations/confirm_delete.html'

    def get_queryset(self):
        return Location.objects.filter(food_truck=self.foodtruck)

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        self.object.is_active = False
        self.object.save(update_fields=['is_active'])
        messages.success(self.request, 'Location marked as inactive.')
        return HttpResponseRedirect(self.get_success_url())

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['foodtruck'] = self.foodtruck
        context['categories'] = self.get_menu_categories()
        return context

    def get_success_url(self):
        return reverse_lazy('orders:location-list', kwargs={'slug': self.foodtruck.slug})


class TicketListView(FoodTruckContextMixin, ListView):
    """Display the authenticated customer's issued tickets for one food truck."""

    model = Ticket
    template_name = 'orders/tickets_list.html'
    context_object_name = 'tickets'

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return super().dispatch(request, *args, **kwargs)
        if kwargs.get('user_id') != request.user.id:
            raise Http404
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        return Ticket.objects.filter(
            order__user_id=self.kwargs['user_id'],
            order__food_truck=self.foodtruck,
        ).select_related(
            'order',
            'order__food_truck',
        ).order_by('-issued_at')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        tickets = context['tickets']
        selected_ticket = None
        selected_ticket_id = self.request.GET.get('ticket')
        if selected_ticket_id:
            selected_ticket = tickets.filter(pk=selected_ticket_id).first()
        elif tickets.count() == 1:
            selected_ticket = tickets.first()

        context.update({
            'foodtruck': self.foodtruck,
            'categories': self.get_menu_categories(),
            'ticket_list_url': reverse(
                'orders:ticket-list-page',
                kwargs={'slug': self.foodtruck.slug, 'user_id': self.request.user.id},
            ),
            'selected_ticket': selected_ticket,
            'selected_ticket_items': selected_ticket.payload.get('items', []) if selected_ticket else [],
        })
        return context


class TicketDetailView(FoodTruckContextMixin, TemplateView):
    """Display one immutable ticket for the authenticated customer."""

    template_name = 'orders/ticket_detail.html'

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return super().dispatch(request, *args, **kwargs)
        if kwargs.get('user_id') != request.user.id:
            raise Http404
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        ticket = get_object_or_404(
            Ticket.objects.select_related('order', 'order__food_truck', 'order__user'),
            pk=self.kwargs['ticket_id'],
            order__user_id=self.kwargs['user_id'],
            order__food_truck=self.foodtruck,
        )
        context.update({
            'foodtruck': self.foodtruck,
            'categories': self.get_menu_categories(),
            'ticket': ticket,
            'ticket_items': ticket.payload.get('items', []),
        })
        return context


class OwnerTicketListView(FoodTruckOwnerMixin, TemplateView):
    """Display issued tickets for the owned food truck grouped by customer."""

    template_name = 'orders/owner_tickets_list.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        tickets = Ticket.objects.filter(order__food_truck=self.foodtruck).select_related(
            'order',
            'order__user',
        ).order_by('-issued_at')

        customer_summaries = (
            tickets.values('order__user_id', 'order__user__email', 'order__user__first_name', 'order__user__last_name')
            .annotate(ticket_count=Count('id'), total_amount_sum=Sum('total_amount'))
            .order_by('-ticket_count', 'order__user__email')
        )

        context.update({
            'foodtruck': self.foodtruck,
            'categories': self.get_menu_categories(),
            'customer_summaries': customer_summaries,
            'tickets': tickets,
            'issued_tickets_count': tickets.count(),
        })
        return context


def _format_base_location(foodtruck):
    """Return the label for the food truck's base location."""
    return _('Base location')


def _load_menu_categories(foodtruck):
    try:
        menu = MenuService.get_active_menu_for_foodtruck(foodtruck.slug)
        return menu.categories.order_by('display_order', 'name')
    except Http404:
        return []
