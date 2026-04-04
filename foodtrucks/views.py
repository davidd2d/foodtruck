from django.shortcuts import get_object_or_404, render

from .models import FoodTruck

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

    return render(request, 'foodtrucks/detail.html', {
        'foodtruck': foodtruck,
    })
