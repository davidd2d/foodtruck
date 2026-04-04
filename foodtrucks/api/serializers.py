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