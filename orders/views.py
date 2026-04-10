from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import Http404, HttpResponseRedirect
from django.shortcuts import render, get_object_or_404
from django.urls import reverse_lazy
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy as _lazy
from django.views.generic import ListView, CreateView, UpdateView, DeleteView

from foodtrucks.models import FoodTruck
from .forms import LocationForm
from .models import Location
from menu.services.menu_service import MenuService

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


def _format_base_location(foodtruck):
    """Return the label for the food truck's base location."""
    return _('Base location')


def _load_menu_categories(foodtruck):
    try:
        menu = MenuService.get_active_menu_for_foodtruck(foodtruck.slug)
        return menu.categories.order_by('display_order', 'name')
    except Http404:
        return []
