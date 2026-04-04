from rest_framework import serializers
from ..models import Menu, Category, Item, OptionGroup, Option


class OptionSerializer(serializers.ModelSerializer):
    """Serializer for Option model."""
    class Meta:
        model = Option
        fields = ['id', 'name', 'price_modifier', 'is_available']


class OptionGroupSerializer(serializers.ModelSerializer):
    """Serializer for OptionGroup model."""
    options = OptionSerializer(many=True, read_only=True)

    class Meta:
        model = OptionGroup
        fields = ['id', 'name', 'required', 'min_choices', 'max_choices', 'options']


class ItemSerializer(serializers.ModelSerializer):
    """Serializer for Item model."""
    option_groups = OptionGroupSerializer(many=True, read_only=True)
    compatible_preferences = serializers.StringRelatedField(many=True, read_only=True)

    class Meta:
        model = Item
        fields = [
            'id', 'name', 'description', 'base_price', 'is_available',
            'display_order', 'compatible_preferences', 'option_groups'
        ]


class CategorySerializer(serializers.ModelSerializer):
    """Serializer for Category model."""
    items = ItemSerializer(many=True, read_only=True)

    class Meta:
        model = Category
        fields = ['id', 'name', 'display_order', 'items']


class MenuSerializer(serializers.ModelSerializer):
    """Serializer for Menu model."""
    categories = CategorySerializer(many=True, read_only=True)

    class Meta:
        model = Menu
        fields = ['id', 'name', 'is_active', 'created_at', 'categories']