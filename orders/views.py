from django.contrib.auth.decorators import login_required
from django.shortcuts import render, get_object_or_404

from foodtrucks.models import FoodTruck


@login_required
def history(request):
    return render(request, 'orders/history.html')


@login_required
def manage_pickup_slots(request, slug):
    """
    Render the management UI for pickup slots for a single food truck.
    """
    foodtruck = get_object_or_404(
        FoodTruck,
        slug=slug,
        owner=request.user,
    )
    return render(request, 'orders/slot_management.html', {
        'foodtruck': foodtruck,
    })
