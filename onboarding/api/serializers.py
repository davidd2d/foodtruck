from rest_framework import serializers
from onboarding.models import OnboardingImport


class OnboardingImportSerializer(serializers.ModelSerializer):
    """Serializer for OnboardingImport model."""

    class Meta:
        model = OnboardingImport
        fields = [
            'id', 'raw_text', 'images', 'source_url',
            'status', 'parsed_data', 'created_at'
        ]
        read_only_fields = ['id', 'status', 'parsed_data', 'created_at']


class OnboardingImportCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating OnboardingImport instances."""

    class Meta:
        model = OnboardingImport
        fields = ['raw_text', 'images', 'source_url']

    def create(self, validated_data):
        validated_data['user'] = self.context['request'].user
        return super().create(validated_data)


class OnboardingPreviewSerializer(serializers.Serializer):
    """Serializer for onboarding preview response."""

    foodtruck = serializers.DictField()
    menu = serializers.ListField()
    branding = serializers.DictField()
    can_create = serializers.BooleanField()


class OnboardingCreateSerializer(serializers.Serializer):
    """Serializer for creating entities from import."""

    import_id = serializers.IntegerField()

    def validate_import_id(self, value):
        try:
            import_instance = OnboardingImport.objects.get(
                id=value,
                user=self.context['request'].user,
                status='completed'
            )
            return value
        except OnboardingImport.DoesNotExist:
            raise serializers.ValidationError("Invalid or incomplete import")