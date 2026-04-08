from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from foodtrucks.models import FoodTruck
from menu.models import Menu

@require_http_methods(["GET"])
def list_foodtrucks_view(request):
    """List all foodtrucks with their menu status."""
    trucks = FoodTruck.objects.all().prefetch_related(
        'menus'
    )
    
    data = {
        'total': trucks.count(),
        'foodtrucks': []
    }
    
    for truck in trucks:
        active_menu = Menu.objects.filter(
            food_truck=truck, 
            is_active=True
        ).first()
        
        data['foodtrucks'].append({
            'id': truck.id,
            'slug': truck.slug,
            'name': truck.name,
            'is_active': truck.is_active,
            'has_active_menu': active_menu is not None,
            'menu_id': active_menu.id if active_menu else None,
        })
    
    return JsonResponse(data, json_dumps_params={'indent': 2})
