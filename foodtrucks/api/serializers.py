from django.conf import settings
from rest_framework import serializers
from ..models import FoodTruck


class FoodTruckSerializer(serializers.ModelSerializer):
    """
    Serializer for FoodTruck model.

    Includes branding, location, and supported preferences.
    """
    supported_preferences = serializers.StringRelatedField(many=True, read_only=True)

    class Meta:
        model = FoodTruck
        fields = [
            'id',
            'slug',
            'default_language',
            'name',
            'description',
            'logo',
            'cover_image',
            'primary_color',
            'secondary_color',
            'latitude',
            'longitude',
            'is_active',
            'supported_preferences',
            'created_at',
        ]
        read_only_fields = ['id', 'created_at']


class CreateWithMenuSerializer(serializers.Serializer):
    """
    Serializer for creating foodtruck with menu.
    """
    name = serializers.CharField(max_length=100)
    description = serializers.CharField()
    default_language = serializers.ChoiceField(
        choices=settings.LANGUAGES,
        required=False,
        default=settings.LANGUAGE_CODE,
    )
    menu = serializers.ListField(child=serializers.DictField())

    def validate_menu(self, value):
        if not value:
            raise serializers.ValidationError("Menu cannot be empty")

        for category in value:
            if not category.get('category'):
                raise serializers.ValidationError("Category name is required")
            if not category.get('items'):
                raise serializers.ValidationError("Category must have items")
            for item in category['items']:
                if not item.get('name'):
                    raise serializers.ValidationError("Item name is required")
                if not isinstance(item.get('price'), (int, float)) or item['price'] <= 0:
                    raise serializers.ValidationError("Item price must be positive")

        return value