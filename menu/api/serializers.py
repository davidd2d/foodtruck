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
    foodtruck = serializers.PrimaryKeyRelatedField(source='food_truck', read_only=True)
    categories = CategorySerializer(many=True, read_only=True)

    class Meta:
        model = Menu
        fields = ['id', 'name', 'foodtruck', 'is_active', 'created_at', 'categories']

    def to_representation(self, instance):
        data = super().to_representation(instance)
        item_search = self.context.get('item_search')
        if item_search:
            normalized_search = item_search.strip().lower()
            categories = []
            for category in data.get('categories', []):
                filtered_items = [
                    item for item in category.get('items', [])
                    if normalized_search in item.get('name', '').lower()
                ]
                if filtered_items:
                    category['items'] = filtered_items
                    categories.append(category)
            data['categories'] = categories
        return data