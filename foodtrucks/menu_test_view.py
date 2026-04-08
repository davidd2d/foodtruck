from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from menu.services.menu_service import MenuService
from django.http import Http404

@require_http_methods(["GET"])
def test_menu_api(request):
    """Test the menu API endpoint directly."""
    slug = request.GET.get('slug', 'cucina-di-pastaz')
    
    result = {
        'slug': slug,
        'status': None,
        'menu': None,
        'error': None,
    }
    
    try:
        menu = MenuService.get_active_menu_for_foodtruck(slug)
        
        result['status'] = 'success'
        result['menu'] = {
            'id': menu.id,
            'name': menu.name,
            'is_active': menu.is_active,
            'foodtruck': menu.food_truck.slug,
            'categories_count': menu.categories.count(),
            'categories': [
                {
                    'id': cat.id,
                    'name': cat.name,
                    'display_order': cat.display_order,
                    'items': [
                        {
                            'id': item.id,
                            'name': item.name,
                            'base_price': str(item.base_price),
                            'is_available': item.is_available,
                        } for item in cat.items.all()[:3]
                    ]
                } for cat in menu.categories.all()
            ]
        }
        
    except Http404 as e:
        result['status'] = 'not_found'
        result['error'] = str(e)
    except Exception as e:
        result['status'] = 'error'
        result['error'] = f"{type(e).__name__}: {str(e)}"
    
    return JsonResponse(result, json_dumps_params={'indent': 2})
