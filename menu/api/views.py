from rest_framework import viewsets, status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from .serializers import MenuSerializer, FoodTruckMenuSerializer
from ..models import Menu
from ..services.menu_service import MenuService


class FoodTruckMenuView(APIView):
    """API endpoint for retrieving a foodtruck menu by slug."""
    permission_classes = [AllowAny]

    def get(self, request, slug):
        menu = MenuService.get_active_menu_for_foodtruck(slug)
        serializer = FoodTruckMenuSerializer(menu, context=self.get_serializer_context())
        return Response(serializer.data, status=status.HTTP_200_OK)

    def get_serializer_context(self):
        return {'request': self.request}


class MenuViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for Menu model.

    Provides read-only access to menus with nested categories and items.
    """
    queryset = Menu.objects.all()
    serializer_class = MenuSerializer
    permission_classes = [AllowAny]

    def get_queryset(self):
        """
        Optimize queryset with nested prefetch_related.
        """
        queryset = Menu.objects.select_related(
            'food_truck'
        ).prefetch_related(
            'categories__items__compatible_preferences',
            'categories__items__option_groups__options',
            'categories__combos__combo_items__item',
            'categories__combos__combo_items__fixed_items',
        ).filter(is_active=True)

        item_search = self.request.query_params.get('item_search')
        if item_search:
            queryset = queryset.filter(
                categories__items__name__icontains=item_search
            ).distinct() | queryset.filter(
                categories__combos__name__icontains=item_search
            ).distinct()

        return queryset

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['item_search'] = self.request.query_params.get('item_search')
        return context