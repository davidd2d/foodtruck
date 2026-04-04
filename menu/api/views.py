from rest_framework import viewsets
from rest_framework.permissions import AllowAny
from .serializers import MenuSerializer
from ..models import Menu


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
            'categories__items__option_groups__options'
        ).filter(is_active=True)

        item_search = self.request.query_params.get('item_search')
        if item_search:
            queryset = queryset.filter(
                categories__items__name__icontains=item_search
            ).distinct()

        return queryset

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['item_search'] = self.request.query_params.get('item_search')
        return context