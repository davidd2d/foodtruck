from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import viewsets, filters, status
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from .serializers import FoodTruckSerializer, CreateWithMenuSerializer
from ..models import FoodTruck
from menu.models import Menu, Category, Item


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

    @action(detail=False, methods=['post'], permission_classes=[IsAuthenticated])
    def create_with_menu(self, request):
        """
        Create foodtruck with menu from AI-generated data.
        """
        serializer = CreateWithMenuSerializer(data=request.data)
        if serializer.is_valid():
            # Create foodtruck
            foodtruck = FoodTruck.objects.create(
                owner=request.user,
                default_language=serializer.validated_data['default_language'],
                name=serializer.validated_data['name'],
                description=serializer.validated_data['description']
            )

            # Create menu
            menu = Menu.objects.create(food_truck=foodtruck, name=foodtruck.get_default_menu_name())

            for category_data in serializer.validated_data['menu']:
                category = Category.objects.create(menu=menu, name=category_data['category'])

                for item_data in category_data['items']:
                    Item.objects.create(
                        category=category,
                        name=item_data['name'],
                        base_price=item_data['price']
                    )

            response_serializer = FoodTruckSerializer(foodtruck)
            return Response(response_serializer.data, status=status.HTTP_201_CREATED)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)