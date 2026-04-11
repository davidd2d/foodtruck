from django.conf import settings
from rest_framework import serializers
from onboarding.models import OnboardingImport, OnboardingImage
import os
from django.conf import settings
from django.core.files.storage import default_storage


class OnboardingImageSerializer(serializers.ModelSerializer):
    """Serializer for OnboardingImage model with direct image URL."""

    class Meta:
        model = OnboardingImage
        fields = ['id', 'url', 'created_at']

    url = serializers.SerializerMethodField()

    def get_url(self, obj):
        return default_storage.url(obj.image.name)


class OnboardingImportSerializer(serializers.ModelSerializer):
    """Serializer for OnboardingImport model."""
    images = OnboardingImageSerializer(many=True, read_only=True, source='image_files')

    class Meta:
        model = OnboardingImport
        fields = [
            'id', 'raw_text', 'images', 'source_url',
            'status', 'parsed_data', 'created_at'
        ]
        read_only_fields = ['status', 'parsed_data', 'created_at']


class OnboardingImportCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating OnboardingImport instances."""
    images = serializers.ListField(
        child=serializers.FileField(),
        required=False,
        allow_empty=True,
        write_only=True
    )
    logo = serializers.FileField(required=False, write_only=True)

    class Meta:
        model = OnboardingImport
        fields = ['id', 'raw_text', 'images', 'logo', 'source_url']

    def create(self, validated_data):
        images_files = validated_data.pop('images', [])
        logo_file = validated_data.pop('logo', None)
        validated_data['user'] = self.context['request'].user

        # Create the import instance first (to get ID)
        import_instance = super().create(validated_data)

        # Save menu images
        for image_file in images_files:
            OnboardingImage.objects.create(
                import_instance=import_instance,
                image=image_file,
                image_type='menu'
            )

        # Save logo if provided
        if logo_file:
            OnboardingImage.objects.create(
                import_instance=import_instance,
                image=logo_file,
                image_type='logo'
            )

        return import_instance


class OnboardingPreviewSerializer(serializers.Serializer):
    """Serializer for onboarding preview response."""

    foodtruck = serializers.DictField()
    menu = serializers.ListField()
    branding = serializers.DictField()
    can_create = serializers.BooleanField()


class GenerateFoodtruckSerializer(serializers.Serializer):
    """Serializer for generating foodtruck with AI."""

    concept = serializers.CharField(max_length=200)
    language_code = serializers.ChoiceField(
        choices=settings.LANGUAGES,
        required=False,
        default=settings.LANGUAGE_CODE,
    )
    cuisine_type = serializers.CharField(max_length=50, required=False, allow_blank=True)
    price_range = serializers.CharField(max_length=20, required=False, allow_blank=True)
    dietary_tags = serializers.ListField(
        child=serializers.CharField(),
        required=False,
        allow_empty=True
    )
