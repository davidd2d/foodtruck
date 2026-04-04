from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from .serializers import (
    OrderSerializer, OrderCreateSerializer, AddItemSerializer
)
from ..models import Order
from menu.models import Item


class OrderViewSet(viewsets.ModelViewSet):
    """
    ViewSet for Order model.

    Handles order creation, item addition, and submission.
    """
    queryset = Order.objects.all()
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['status', 'food_truck']

    def get_serializer_class(self):
        if self.action == 'create':
            return OrderCreateSerializer
        return OrderSerializer

    def get_queryset(self):
        """
        Return orders for the current user only.
        Optimize with select_related and prefetch_related.
        """
        return Order.objects.filter(
            customer=self.request.user
        ).select_related(
            'food_truck', 'pickup_slot'
        ).prefetch_related(
            'items__selected_options__option',
            'items__item'
        )

    def perform_create(self, serializer):
        """Create order for the current user."""
        serializer.save(customer=self.request.user)

    def create(self, request, *args, **kwargs):
        """Create an order and return the full serialized object."""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        # Return the created object with full serialization
        instance = serializer.instance
        response_serializer = OrderSerializer(instance)
        headers = self.get_success_headers(response_serializer.data)
        return Response(response_serializer.data, status=status.HTTP_201_CREATED, headers=headers)

    @action(detail=True, methods=['post'])
    def add_item(self, request, pk=None):
        """
        Add an item to the order.

        Expects: item_id, quantity, selected_options (optional)
        """
        order = self.get_object()
        serializer = AddItemSerializer(data=request.data)

        if serializer.is_valid():
            try:
                item = Item.objects.get(id=serializer.validated_data['item_id'])
                order.add_item(
                    item=item,
                    quantity=serializer.validated_data['quantity'],
                    selected_options=serializer.validated_data.get('selected_options', [])
                )
                return Response({'status': 'item added'}, status=status.HTTP_200_OK)
            except Item.DoesNotExist:
                return Response({'error': 'Item not found'}, status=status.HTTP_404_NOT_FOUND)
            except Exception as e:
                return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'])
    def submit(self, request, pk=None):
        """
        Submit the order for processing.
        """
        order = self.get_object()

        try:
            order.submit()
            return Response({'status': 'order submitted'}, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)