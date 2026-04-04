from django.utils import timezone
from rest_framework import serializers

from ..models import Order, OrderItem, OrderItemOption, PickupSlot


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


class PickupSlotSerializer(serializers.ModelSerializer):
    """Serializer for PickupSlot model."""
    remaining_capacity = serializers.SerializerMethodField()
    is_available = serializers.SerializerMethodField()

    class Meta:
        model = PickupSlot
        fields = [
            'id',
            'start_time',
            'end_time',
            'capacity',
            'remaining_capacity',
            'is_available',
        ]

    def get_remaining_capacity(self, obj):
        reserved = getattr(obj, 'reserved_orders', None)
        if reserved is not None:
            return max(0, obj.capacity - reserved)
        return obj.remaining_capacity()

    def get_is_available(self, obj):
        remaining = self.get_remaining_capacity(obj)
        return obj.start_time >= timezone.now() and remaining > 0


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
