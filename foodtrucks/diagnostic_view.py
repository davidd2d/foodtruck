from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from foodtrucks.models import FoodTruck
from menu.models import Menu, Category, Item
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods

@login_required
@require_http_methods(["GET"])
def diagnostic_view(request):
    """Diagnostic view to troubleshoot menu display issues."""
    # Only allow staff
    if not request.user.is_staff:
        return JsonResponse({'error': 'Staff access required'}, status=403)
    
    slug = request.GET.get('slug', 'cucina-di-pastaz')
    
    truck = FoodTruck.objects.filter(slug=slug).first()
    diagnostic = {
        'slug': slug,
        'foodtruck_found': truck is not None,
        'foodtruck': None,
        'menus': [],
        'active_menu': None,
    }
    
    if truck:
        diagnostic['foodtruck'] = {
            'id': truck.id,
            'name': truck.name,
            'slug': truck.slug,
            'is_active': truck.is_active,
        }
        
        # Get all menus
        menus = Menu.objects.filter(food_truck=truck).prefetch_related(
            'categories__items'
        )
        diagnostic['menus'] = [{
            'id': m.id,
            'name': m.name,
            'is_active': m.is_active,
            'category_count': m.categories.count(),
            'item_count': Item.objects.filter(category__menu=m).count(),
        } for m in menus]
        
        # Get active menu
        active_menu = Menu.objects.filter(food_truck=truck, is_active=True).prefetch_related(
            'categories__items'
        ).first()
        
        if active_menu:
            categories_data = []
            for cat in active_menu.categories.all():
                items = cat.items.all()
                categories_data.append({
                    'id': cat.id,
                    'name': cat.name,
                    'item_count': items.count(),
                    'items': [{'id': i.id, 'name': i.name, 'price': str(i.base_price)} for i in items[:3]]
                })
            
            diagnostic['active_menu'] = {
                'id': active_menu.id,
                'name': active_menu.name,
                'created_at': str(active_menu.created_at),
                'categories': categories_data,
            }
    
    return JsonResponse(diagnostic, json_dumps_params={'indent': 2})
