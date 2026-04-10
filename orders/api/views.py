from datetime import datetime, timedelta
import logging

from django.core.exceptions import ValidationError
from django.db.models import Count, Q
from django.utils import timezone
from datetime import datetime

from rest_framework import viewsets, status
from rest_framework import permissions
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAuthenticated, BasePermission
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.exceptions import ValidationError as DRFValidationError
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
    PickupSlotManageSerializer,
    OrderSlotAssignmentSerializer,
    OrderSubmissionSerializer,
    ServiceScheduleSerializer,
)
from ..models import Order, PickupSlot, ServiceSchedule, PARIS_TZ
from menu.models import Combo, Item
from ..services.cart_service import CartService
from ..services.order_service import OrderService
from ..services.schedule_service import generate_slots_for_date
from foodtrucks.models import FoodTruck
import logging


class IsFoodTruckOwner(BasePermission):
    """Object permission to ensure the user is the owner of the related food truck."""

    def has_object_permission(self, request, view, obj):
        return getattr(obj.food_truck, 'owner_id', None) == request.user.id


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
                if serializer.validated_data.get('combo_id'):
                    combo = Combo.objects.get(id=serializer.validated_data['combo_id'])
                    order.add_combo(
                        combo=combo,
                        quantity=serializer.validated_data['quantity'],
                    )
                else:
                    item = Item.objects.get(id=serializer.validated_data['item_id'])
                    order.add_item(
                        item=item,
                        quantity=serializer.validated_data['quantity'],
                        selected_options=serializer.validated_data.get('selected_options', [])
                    )
                return Response({'status': 'item added'}, status=status.HTTP_200_OK)
            except (Item.DoesNotExist, Combo.DoesNotExist):
                return Response({'error': 'Product not found'}, status=status.HTTP_404_NOT_FOUND)
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
                cart_service = CartService(request.session)
                if serializer.validated_data.get('combo_id'):
                    cart_service.add_combo(
                        foodtruck_slug=serializer.validated_data['foodtruck_slug'],
                        combo_id=serializer.validated_data['combo_id'],
                        quantity=serializer.validated_data['quantity'],
                    )
                else:
                    cart_service.add_item(
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
        logger = logging.getLogger(__name__)
        date_param = request.query_params.get('date')
        try:
            food_truck = FoodTruck.objects.get(slug=slug, is_active=True)
        except FoodTruck.DoesNotExist:
            logger.warning("Requested slots for unknown food truck slug=%s", slug)
            return Response({'detail': 'Food truck not found.'}, status=status.HTTP_404_NOT_FOUND)

        if date_param:
            try:
                target_date = datetime.strptime(date_param, '%Y-%m-%d').date()
            except ValueError:
                return Response({'detail': 'Invalid date format. Use YYYY-MM-DD.'}, status=status.HTTP_400_BAD_REQUEST)
            generate_slots_for_date(food_truck, target_date)
            slots = food_truck.get_available_slots(target_date).select_related('food_truck')
        else:
            slots = food_truck.get_recommended_pickup_slots().select_related('food_truck')
            first_slot = slots.first()
            target_date = first_slot.start_time.date() if first_slot else timezone.localdate()

        serializer = PickupSlotSerializer(slots, many=True)
        logger.info("Returning %s slots for food truck %s on %s", len(slots), food_truck.slug, target_date)
        return Response(serializer.data, status=status.HTTP_200_OK)


class ServiceScheduleViewSet(viewsets.ModelViewSet):
    """Allow owners to manage their service schedules."""

    serializer_class = ServiceScheduleSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return ServiceSchedule.objects.filter(
            food_truck__owner=self.request.user
        ).select_related('food_truck', 'location')

    def list(self, request, *args, **kwargs):
        logger = logging.getLogger(__name__)
        date_param = request.query_params.get('date')
        if date_param:
            try:
                target_date = datetime.strptime(date_param, '%Y-%m-%d').date()
            except ValueError:
                logger.warning('Invalid date "%s" for schedule list', date_param)
                return Response({'detail': 'Invalid date format. Use YYYY-MM-DD.'}, status=status.HTTP_400_BAD_REQUEST)
        else:
            target_date = timezone.localdate()

        queryset = self.filter_queryset(self.get_queryset())
        schedules = queryset.select_related('food_truck')
        processed = set()
        for schedule in schedules:
            target = self._resolve_target_date_for_schedule(schedule, target_date)
            generate_slots_for_date(schedule.food_truck, target)
            processed.add((schedule.food_truck.id, target))
        logger.info('Triggered slot generation for %s schedule instances on %s', len(processed), target_date)
        return super().list(request, *args, **kwargs)

    def _resolve_target_date_for_schedule(self, schedule, reference_date):
        days_ahead = (schedule.day_of_week - reference_date.weekday() + 7) % 7
        return reference_date + timedelta(days=days_ahead)

    def perform_create(self, serializer):
        food_truck = self._get_owner_food_truck()
        schedule = serializer.save(food_truck=food_truck)
        target_date = self._next_target_date(schedule.day_of_week)
        logger = logging.getLogger(__name__)
        logger.info('Auto-generating slots for schedule %s on %s', schedule.id, target_date)
        generate_slots_for_date(food_truck, target_date)

    def _next_target_date(self, day_of_week):
        today = timezone.localdate()
        days_ahead = (day_of_week - today.weekday() + 7) % 7
        if days_ahead == 0:
            days_ahead = 7
        return today + timedelta(days=days_ahead)
    def _get_owner_food_truck(self):
        from foodtrucks.models import FoodTruck

        food_truck = FoodTruck.objects.filter(owner=self.request.user, is_active=True).first()
        if not food_truck:
            raise DRFValidationError({'food_truck': 'No active food truck found for this user.'})
        return food_truck


class PickupSlotViewSet(viewsets.ReadOnlyModelViewSet):
    """Expose generated pickup slots for a food truck."""

    serializer_class = PickupSlotSerializer
    permission_classes = [AllowAny]
    queryset = PickupSlot.objects.select_related('food_truck').all()
    def list(self, request, *args, **kwargs):
        self._food_truck = self._get_food_truck(request)
        self._target_date = self._get_target_date(request)
        generate_slots_for_date(self._food_truck, self._target_date)
        return super().list(request, *args, **kwargs)

    def get_queryset(self):
        queryset = super().get_queryset()
        if not hasattr(self, '_food_truck'):
            return queryset.none()

        return queryset.filter(
            food_truck=self._food_truck,
            start_time__date=self._target_date
        ).annotate(
            reserved=Count(
                'orders',
                filter=Q(orders__status__in=['draft', 'submitted', 'paid'])
            )
        ).order_by('start_time')

    def _get_food_truck(self, request):
        slug = request.query_params.get('foodtruck_slug')
        if not slug:
            raise DRFValidationError({'foodtruck_slug': 'This parameter is required.'})

        try:
            return FoodTruck.objects.get(slug=slug, is_active=True)
        except FoodTruck.DoesNotExist:
            raise DRFValidationError({'foodtruck_slug': 'Food truck not found.'})

    def _get_target_date(self, request):
        date_param = request.query_params.get('date')
        if date_param:
            try:
                return datetime.strptime(date_param, '%Y-%m-%d').date()
            except ValueError:
                raise DRFValidationError({'date': 'Invalid date format. Use YYYY-MM-DD.'})
        return timezone.localdate()


class PickupSlotManageViewSet(viewsets.ModelViewSet):
    """Allow food truck owners to manage their pickup slots."""

    serializer_class = PickupSlotManageSerializer
    permission_classes = [IsAuthenticated, IsFoodTruckOwner]

    def get_queryset(self):
        """Return slots belonging to the logged-in owner."""
        slug = self.request.query_params.get('foodtruck_slug')
        queryset = PickupSlot.objects.filter(
            food_truck__owner=self.request.user
        ).order_by('start_time').select_related('food_truck')

        if slug:
            queryset = queryset.filter(food_truck__slug=slug)

        return queryset

    def perform_create(self, serializer):
        """Ensure the serializer enforces ownership."""
        serializer.save()
