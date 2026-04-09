from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from rest_framework import serializers

import pytz

from ..models import Order, OrderItem, OrderItemOption, PickupSlot, ServiceSchedule

PARIS_TZ = pytz.timezone('Europe/Paris')


class OrderItemOptionSerializer(serializers.ModelSerializer):
    """Serializer for OrderItemOption model."""
    class Meta:
        model = OrderItemOption
        fields = ['id', 'option', 'price_modifier']


class OrderItemSerializer(serializers.ModelSerializer):
    """Serializer for OrderItem model."""
    selected_options = OrderItemOptionSerializer(many=True, read_only=True)

    class Meta:
        model = OrderItem
        fields = [
            'id', 'item', 'quantity', 'unit_price', 'total_price', 'selected_options'
        ]


class ServiceScheduleSerializer(serializers.ModelSerializer):
    """Serializer for ServiceSchedule model."""

    location_label = serializers.SerializerMethodField()

    class Meta:
        model = ServiceSchedule
        fields = [
            'id',
            'day_of_week',
            'start_time',
            'end_time',
            'capacity_per_slot',
            'slot_duration_minutes',
            'is_active',
            'location',
            'location_label',
        ]

    def get_location_label(self, obj):
        if obj.location:
            return obj.location.name or obj.location.get_full_address()
        return _('Base location')

    def validate(self, attrs):
        start = attrs.get('start_time', getattr(self.instance, 'start_time', None))
        end = attrs.get('end_time', getattr(self.instance, 'end_time', None))
        food_truck = attrs.get('food_truck', getattr(self.instance, 'food_truck', None))
        day_of_week = attrs.get('day_of_week', getattr(self.instance, 'day_of_week', None))

        if food_truck is None:
            request = self.context.get('request')
            if request:
                from foodtrucks.models import FoodTruck

                food_truck = FoodTruck.objects.filter(owner=request.user, is_active=True).first()

        if start is None or end is None or food_truck is None or day_of_week is None:
            return attrs

        if start >= end:
            raise serializers.ValidationError({'end_time': 'end_time must be after start_time.'})

        if food_truck is None:
            raise serializers.ValidationError({'food_truck': 'Food truck must be set.'})

        overlapping = ServiceSchedule.objects.filter(
            food_truck=food_truck,
            day_of_week=day_of_week,
            is_active=True,
        )
        if self.instance:
            overlapping = overlapping.exclude(pk=self.instance.pk)

        for other in overlapping:
            if start < other.end_time and end > other.start_time:
                raise serializers.ValidationError("This schedule overlaps with an existing one.")

        return attrs


class PickupSlotSerializer(serializers.ModelSerializer):
    """Serializer for PickupSlot model."""
    remaining_capacity = serializers.SerializerMethodField()
    is_available = serializers.SerializerMethodField()
    reserved = serializers.IntegerField(read_only=True)

    class Meta:
        model = PickupSlot
        fields = [
            'id',
            'start_time',
            'end_time',
            'capacity',
            'remaining_capacity',
            'is_available',
            'reserved',
            'service_schedule',
        ]

    def get_remaining_capacity(self, obj):
        reserved = getattr(obj, 'reserved', None)
        if reserved is not None:
            return max(0, obj.capacity - reserved)
        return obj.remaining_capacity()

    def get_is_available(self, obj):
        remaining = self.get_remaining_capacity(obj)
        return obj.start_time >= timezone.now() and remaining > 0


class PickupSlotManageSerializer(serializers.ModelSerializer):
    """Serializer used by food truck owners to manage slots."""

    remaining_capacity = serializers.IntegerField(read_only=True)
    current_bookings = serializers.IntegerField(read_only=True)
    is_available = serializers.SerializerMethodField()
    food_truck_id = serializers.IntegerField(write_only=True, required=False)

    class Meta:
        model = PickupSlot
        fields = [
            'id',
            'food_truck_id',
            'food_truck',
            'start_time',
            'end_time',
            'capacity',
            'remaining_capacity',
            'current_bookings',
            'is_available',
        ]

    food_truck = serializers.ReadOnlyField(source='food_truck.slug')

    def get_is_available(self, obj):
        return obj.is_available()

    def validate(self, attrs):
        data = dict(attrs)
        start_time = data.get('start_time') or getattr(self.instance, 'start_time', None)
        end_time = data.get('end_time') or getattr(self.instance, 'end_time', None)

        if not start_time or not end_time:
            raise serializers.ValidationError('Both start_time and end_time are required.')

        if start_time >= end_time:
            raise serializers.ValidationError('end_time must be after start_time.')

        paris_now = timezone.localtime(timezone.now(), PARIS_TZ)
        if start_time <= paris_now:
            raise serializers.ValidationError('Pickup slot must be scheduled in the future (Paris time).')

        food_truck = self._resolve_food_truck(data)
        overlapping = PickupSlot.objects.filter(
            food_truck=food_truck,
            start_time__lt=end_time,
            end_time__gt=start_time,
        )
        if self.instance:
            overlapping = overlapping.exclude(pk=self.instance.pk)

        if overlapping.exists():
            raise serializers.ValidationError('This slot overlaps with an existing slot.')

        return attrs

    def _resolve_food_truck(self, data):
        from foodtrucks.models import FoodTruck

        if self.instance:
            return self.instance.food_truck

        food_truck_id = data.get('food_truck_id')
        if not food_truck_id:
            raise serializers.ValidationError('food_truck_id is required.')

        try:
            food_truck = FoodTruck.objects.get(pk=food_truck_id)
        except FoodTruck.DoesNotExist:
            raise serializers.ValidationError('Food truck does not exist.')

        request = self.context.get('request')
        if request and food_truck.owner_id != request.user.id:
            raise serializers.ValidationError('You do not own this food truck.')

        return food_truck

    def create(self, validated_data):
        food_truck_id = validated_data.pop('food_truck_id', None)
        food_truck = self._resolve_food_truck({'food_truck_id': food_truck_id})
        validated_data['food_truck'] = food_truck
        return super().create(validated_data)

    def update(self, instance, validated_data):
        validated_data.pop('food_truck_id', None)
        return super().update(instance, validated_data)

class OrderSerializer(serializers.ModelSerializer):
    """Serializer for Order model."""
    items = OrderItemSerializer(many=True, read_only=True)
    pickup_slot = PickupSlotSerializer(read_only=True)
    customer = serializers.PrimaryKeyRelatedField(source='user', read_only=True)

    class Meta:
        model = Order
        fields = [
            'id', 'customer', 'food_truck', 'pickup_slot', 'status',
            'total_price', 'created_at', 'items'
        ]
        read_only_fields = ['id', 'customer', 'status', 'total_price', 'created_at']


class OrderCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating orders."""
    class Meta:
        model = Order
        fields = ['food_truck', 'pickup_slot']


class AddItemSerializer(serializers.Serializer):
    """Serializer for adding items to order."""
    item_id = serializers.IntegerField()
    quantity = serializers.IntegerField(min_value=1)
    selected_options = serializers.ListField(
        child=serializers.IntegerField(),
        required=False,
        allow_empty=True
    )


class CartItemSerializer(serializers.Serializer):
    """Serializer for cart item payload."""
    line_key = serializers.CharField()
    item_id = serializers.IntegerField()
    item_name = serializers.CharField()
    quantity = serializers.IntegerField()
    unit_price = serializers.DecimalField(max_digits=10, decimal_places=2)
    total_price = serializers.DecimalField(max_digits=10, decimal_places=2)
    selected_options = serializers.ListField(child=serializers.DictField(), required=False)


class CartSerializer(serializers.Serializer):
    """Serializer for cart payload."""
    foodtruck_slug = serializers.CharField(allow_null=True)
    items = CartItemSerializer(many=True)
    total_price = serializers.DecimalField(max_digits=10, decimal_places=2)
    item_count = serializers.IntegerField()


class AddCartItemSerializer(serializers.Serializer):
    """Serializer for adding an item to the cart."""
    foodtruck_slug = serializers.SlugField()
    item_id = serializers.IntegerField()
    quantity = serializers.IntegerField(min_value=1)
    selected_options = serializers.ListField(
        child=serializers.IntegerField(),
        required=False,
        allow_empty=True
    )


class RemoveCartItemSerializer(serializers.Serializer):
    """Serializer for removing an item from the cart."""
    line_key = serializers.CharField()


class CartCheckoutSerializer(serializers.Serializer):
    """Serializer for creating an order from the cart."""
    pickup_slot = serializers.IntegerField(required=False)


class OrderSlotAssignmentSerializer(serializers.Serializer):
    """Serializer for assigning a pickup slot to an existing draft order."""
    order_id = serializers.IntegerField()
    pickup_slot = serializers.IntegerField()


class OrderSubmissionSerializer(serializers.Serializer):
    """Serializer for submitting a draft order."""
    order_id = serializers.IntegerField()
