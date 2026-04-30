from rest_framework import serializers
from ..models import Menu, Category, Item, Combo, ComboItem, OptionGroup, Option


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
    option_groups = serializers.SerializerMethodField()
    compatible_preferences = serializers.StringRelatedField(many=True, read_only=True)
    display_price = serializers.SerializerMethodField()
    tax_rate = serializers.SerializerMethodField()
    prices_include_tax = serializers.SerializerMethodField()

    class Meta:
        model = Item
        fields = [
            'id', 'name', 'description', 'base_price', 'is_available',
            'display_order', 'compatible_preferences', 'option_groups', 'display_price', 'tax_rate', 'prices_include_tax'
        ]

    def get_tax_rate(self, obj):
        return obj.get_tax_rate()

    def get_display_price(self, obj):
        foodtruck = obj.category.menu.food_truck
        return foodtruck.get_display_price(obj.base_price, obj.get_tax_rate())

    def get_prices_include_tax(self, obj):
        return obj.category.menu.food_truck.prices_include_tax()

    def get_option_groups(self, obj):
        options = obj.available_options.select_related('group').filter(
            group__category=obj.category,
        ).order_by('group__name', 'name')

        grouped = {}
        for option in options:
            group = option.group
            payload = grouped.setdefault(group.id, {
                'id': group.id,
                'name': group.name,
                'required': group.required,
                'min_choices': group.min_choices,
                'max_choices': group.max_choices,
                'options': [],
            })
            payload['options'].append(OptionSerializer(option, context=self.context).data)

        return list(grouped.values())


class ComboItemSerializer(serializers.ModelSerializer):
    """Serializer for ComboItem model."""
    item_id = serializers.SerializerMethodField()
    fixed_item_ids = serializers.SerializerMethodField()
    fixed_items = serializers.SerializerMethodField()
    source_category_id = serializers.IntegerField(source='source_category.id', read_only=True)
    source_category_name = serializers.CharField(source='source_category.name', read_only=True)

    class Meta:
        model = ComboItem
        fields = [
            'id', 'item_id', 'fixed_item_ids', 'fixed_items', 'source_category_id',
            'source_category_name', 'display_name', 'quantity', 'display_order'
        ]

    def get_item_id(self, obj):
        fixed_ids = self.get_fixed_item_ids(obj)
        if fixed_ids:
            return fixed_ids[0]
        return None

    def get_fixed_item_ids(self, obj):
        fixed_ids = list(obj.fixed_items.values_list('id', flat=True))
        if fixed_ids:
            return fixed_ids
        if obj.item_id:
            return [obj.item_id]
        return []

    def get_fixed_items(self, obj):
        fixed_qs = obj.fixed_items.all()
        if fixed_qs.exists():
            return [
                {
                    'id': item.id,
                    'name': item.name,
                    'base_price': str(item.base_price),
                    'is_available': item.is_available,
                }
                for item in fixed_qs
            ]

        if obj.item_id:
            return [{
                'id': obj.item.id,
                'name': obj.item.name,
                'base_price': str(obj.item.base_price),
                'is_available': obj.item.is_available,
            }]

        return []


class ComboSerializer(serializers.ModelSerializer):
    """Serializer for Combo model."""
    combo_items = ComboItemSerializer(many=True, read_only=True)
    effective_price = serializers.SerializerMethodField()
    is_customizable = serializers.BooleanField(read_only=True)
    display_price = serializers.SerializerMethodField()
    tax_rate = serializers.SerializerMethodField()
    prices_include_tax = serializers.SerializerMethodField()

    class Meta:
        model = Combo
        fields = [
            'id', 'name', 'description', 'combo_price', 'discount_amount', 'effective_price',
            'is_available', 'display_order', 'combo_items', 'is_customizable', 'display_price', 'tax_rate', 'prices_include_tax'
        ]

    def get_effective_price(self, obj):
        price = obj.get_effective_price()
        return price

    def get_tax_rate(self, obj):
        return obj.get_tax_rate()

    def get_display_price(self, obj):
        price = obj.get_effective_price()
        if price is None:
            return None
        return obj.category.menu.food_truck.get_display_price(price, obj.get_tax_rate())

    def get_prices_include_tax(self, obj):
        return obj.category.menu.food_truck.prices_include_tax()


class CategorySerializer(serializers.ModelSerializer):
    """Serializer for Category model."""
    items = ItemSerializer(many=True, read_only=True)
    combos = ComboSerializer(many=True, read_only=True)

    class Meta:
        model = Category
        fields = ['id', 'name', 'display_order', 'items', 'combos']


class MenuSerializer(serializers.ModelSerializer):
    """Serializer for Menu model."""
    foodtruck = serializers.PrimaryKeyRelatedField(source='food_truck', read_only=True)
    categories = CategorySerializer(many=True, read_only=True)
    prices_include_tax = serializers.SerializerMethodField()
    price_display_mode = serializers.CharField(source='food_truck.price_display_mode', read_only=True)

    class Meta:
        model = Menu
        fields = ['id', 'name', 'foodtruck', 'is_active', 'created_at', 'categories', 'prices_include_tax', 'price_display_mode']

    def get_prices_include_tax(self, obj):
        return obj.food_truck.prices_include_tax()

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
                filtered_combos = [
                    combo for combo in category.get('combos', [])
                    if normalized_search in combo.get('name', '').lower()
                ]
                if filtered_items or filtered_combos:
                    category['items'] = filtered_items
                    category['combos'] = filtered_combos
                    categories.append(category)
            data['categories'] = categories
        return data


class FoodTruckMenuSerializer(MenuSerializer):
    """Serializer for active foodtruck menu endpoint."""
    foodtruck = serializers.SlugRelatedField(source='food_truck', read_only=True, slug_field='slug')

    class Meta(MenuSerializer.Meta):
        fields = ['id', 'name', 'foodtruck', 'is_active', 'created_at', 'categories', 'prices_include_tax', 'price_display_mode']
