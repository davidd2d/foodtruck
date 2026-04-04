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
    class Meta:
        model = PickupSlot
        fields = ['id', 'start_time', 'end_time', 'capacity']


class OrderSerializer(serializers.ModelSerializer):
    """Serializer for Order model."""
    items = OrderItemSerializer(many=True, read_only=True)
    pickup_slot = PickupSlotSerializer(read_only=True)

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