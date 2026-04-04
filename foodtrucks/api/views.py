from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import viewsets, filters
from rest_framework.permissions import AllowAny
from .serializers import FoodTruckSerializer
from ..models import FoodTruck


class FoodTruckViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for FoodTruck model.

    Provides read-only access to food trucks with filtering and search.
    """
    queryset = FoodTruck.objects.all()
    serializer_class = FoodTruckSerializer
    permission_classes = [AllowAny]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['is_active', 'supported_preferences']
    search_fields = ['name', 'description']
    ordering_fields = ['name', 'created_at', 'distance']  # distance needs custom implementation
    ordering = ['-created_at']

    def get_queryset(self):
        """
        Optimize queryset with select_related and prefetch_related.
        """
        return FoodTruck.objects.select_related(
            'owner',
            'subscription__plan'
        ).prefetch_related(
            'supported_preferences'
        ).active()

    def filter_queryset(self, queryset):
        """
        Custom filtering for distance-based search.
        """
        queryset = super().filter_queryset(queryset)

        # Handle distance filtering if lat/lng provided
        lat = self.request.query_params.get('lat')
        lng = self.request.query_params.get('lng')
        radius = self.request.query_params.get('radius_km') or self.request.query_params.get('radius') or 10

        if lat and lng:
            try:
                lat = float(lat)
                lng = float(lng)
                radius = float(radius)
                queryset = queryset.nearby(lat, lng, radius)
            except ValueError:
                pass  # Ignore invalid parameters

        return queryset