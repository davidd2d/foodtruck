from django.core.exceptions import ValidationError
from django.db.models import Count, Q
from django.utils import timezone

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from django_filters.rest_framework import DjangoFilterBackend
from .serializers import (
    OrderSerializer,
    OrderCreateSerializer,
    AddItemSerializer,
    CartSerializer,
    AddCartItemSerializer,
    RemoveCartItemSerializer,
    CartCheckoutSerializer,
    PickupSlotSerializer,
    OrderSlotAssignmentSerializer,
    OrderSubmissionSerializer,
)
from ..models import Order, PickupSlot
from ..services.cart_service import CartService
from ..services.order_service import OrderService
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
            user=self.request.user
        ).select_related(
            'user', 'food_truck', 'pickup_slot'
        ).prefetch_related(
            'items__selected_options__option',
            'items__item'
        )

    def perform_create(self, serializer):
        """Create order for the current user."""
        serializer.save(user=self.request.user)

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
            OrderService.submit_order(order)
            return Response({'status': 'order submitted'}, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


class CartView(APIView):
    """Retrieve the current session cart."""
    permission_classes = [AllowAny]

    def get(self, request):
        cart = CartService(request.session).get_cart()
        serializer = CartSerializer(cart)
        return Response(serializer.data, status=status.HTTP_200_OK)


class CartAddView(APIView):
    """Add an item to the session cart."""
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = AddCartItemSerializer(data=request.data)
        if serializer.is_valid():
            try:
                CartService(request.session).add_item(
                    foodtruck_slug=serializer.validated_data['foodtruck_slug'],
                    item_id=serializer.validated_data['item_id'],
                    quantity=serializer.validated_data['quantity'],
                    selected_options=serializer.validated_data.get('selected_options', []),
                )
                cart = CartService(request.session).get_cart()
                return Response(cart, status=status.HTTP_200_OK)
            except ValidationError as ex:
                return Response({'error': str(ex)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class CartRemoveView(APIView):
    """Remove an item from the session cart."""
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = RemoveCartItemSerializer(data=request.data)
        if serializer.is_valid():
            try:
                CartService(request.session).remove_item(serializer.validated_data['line_key'])
                cart = CartService(request.session).get_cart()
                return Response(cart, status=status.HTTP_200_OK)
            except ValidationError as ex:
                return Response({'error': str(ex)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class CartCheckoutView(APIView):
    """Create an order from the current session cart."""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = CartCheckoutSerializer(data=request.data)
        if serializer.is_valid():
            try:
                order = OrderService.create_order_from_cart(
                    user=request.user,
                    pickup_slot_id=serializer.validated_data.get('pickup_slot'),
                    session=request.session,
                )
                return Response({'status': 'order created', 'order_id': order.id}, status=status.HTTP_201_CREATED)
            except ValidationError as ex:
                return Response({'error': str(ex)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class SetOrderPickupSlotView(APIView):
    """Assign a pickup slot to a draft order."""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = OrderSlotAssignmentSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        order = Order.objects.filter(
            pk=serializer.validated_data['order_id'],
            user=request.user,
        ).select_related('food_truck', 'pickup_slot').first()

        if not order:
            return Response({'error': 'Order not found.'}, status=status.HTTP_404_NOT_FOUND)

        try:
            OrderService.assign_pickup_slot(order, serializer.validated_data['pickup_slot'])
            return Response({'status': 'pickup slot assigned', 'order_id': order.id}, status=status.HTTP_200_OK)
        except ValidationError as ex:
            return Response({'error': str(ex)}, status=status.HTTP_400_BAD_REQUEST)


class SubmitOrderView(APIView):
    """Submit a draft order once it has a pickup slot."""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = OrderSubmissionSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        order = Order.objects.filter(
            pk=serializer.validated_data['order_id'],
            user=request.user,
        ).select_related('pickup_slot', 'food_truck').first()

        if not order:
            return Response({'error': 'Order not found.'}, status=status.HTTP_404_NOT_FOUND)

        try:
            OrderService.submit_order(order)
            return Response({'status': 'order submitted', 'order_id': order.id}, status=status.HTTP_200_OK)
        except ValidationError as ex:
            return Response({'error': str(ex)}, status=status.HTTP_400_BAD_REQUEST)


class PickupSlotListView(APIView):
    """List available pickup slots for a foodtruck."""
    permission_classes = [AllowAny]

    def get(self, request, slug):
        slots = (
            PickupSlot.objects.filter(
                food_truck__slug=slug,
                start_time__gte=timezone.now(),
            )
            .select_related('food_truck')
            .annotate(
                reserved_orders=Count(
                    'orders',
                    filter=Q(orders__status__in=['draft', 'submitted', 'paid'])
                )
            )
            .order_by('start_time')
        )

        serializer = PickupSlotSerializer(slots, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)
