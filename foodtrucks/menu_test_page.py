from django.shortcuts import render
from django.views.decorators.http import require_http_methods

@require_http_methods(["GET"])
def menu_test_page(request):
    """Test page to debug menu API."""
    return render(request, 'menu_test.html')
