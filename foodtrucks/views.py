from django.http import Http404
from django.shortcuts import get_object_or_404, render

from .models import FoodTruck
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

    # Get available pickup slots and default recommendation
    available_slots = []
    default_slot_id = None
    if foodtruck.can_accept_orders():
        available_slots = foodtruck.get_available_slots()
        default_slot = foodtruck.get_best_default_pickup_slot()
        if default_slot:
            default_slot_id = default_slot.id

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
