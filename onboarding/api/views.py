from rest_framework import status, generics
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.viewsets import ModelViewSet
from django.shortcuts import get_object_or_404

from onboarding.models import OnboardingImport
from onboarding.services.ai_onboarding import AIOnboardingService
from .serializers import (
    OnboardingImportSerializer,
    OnboardingImportCreateSerializer,
    OnboardingPreviewSerializer,
    OnboardingCreateSerializer
)


class OnboardingImportViewSet(ModelViewSet):
    """ViewSet for managing OnboardingImport instances."""

    permission_classes = [IsAuthenticated]
    serializer_class = OnboardingImportSerializer

    def get_queryset(self):
        return OnboardingImport.objects.filter(user=self.request.user)

    def get_serializer_class(self):
        if self.action == 'create':
            return OnboardingImportCreateSerializer
        return super().get_serializer_class()

    def perform_create(self, serializer):
        import_instance = serializer.save()

        # Trigger async processing (for now, sync)
        service = AIOnboardingService()
        result = service.process_import(import_instance.id)

        # Update the instance with the result
        import_instance.refresh_from_db()

        return import_instance

    @action(detail=True, methods=['get'])
    def preview(self, request, pk=None):
        """Get preview of parsed data before creating entities."""
        import_instance = get_object_or_404(
            OnboardingImport,
            id=pk,
            user=request.user
        )

        if import_instance.status != 'completed':
            return Response(
                {'error': 'Import is not yet processed'},
                status=status.HTTP_400_BAD_REQUEST
            )

        serializer = OnboardingPreviewSerializer({
            'foodtruck': import_instance.parsed_data.get('foodtruck', {}),
            'menu': import_instance.parsed_data.get('menu', []),
            'branding': import_instance.parsed_data.get('branding', {}),
            'can_create': bool(import_instance.parsed_data)
        })

        return Response(serializer.data)

    @action(detail=False, methods=['post'])
    def create_from_import(self, request):
        """Create FoodTruck and related entities from processed import."""
        serializer = OnboardingCreateSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)

        import_id = serializer.validated_data['import_id']
        import_instance = get_object_or_404(
            OnboardingImport,
            id=import_id,
            user=request.user,
            status='completed'
        )

        service = AIOnboardingService()
        try:
            result = service.create_foodtruck_from_import(import_instance)
            return Response(result, status=status.HTTP_201_CREATED)
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )