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
    GenerateFoodtruckSerializer
)


class OnboardingImportViewSet(ModelViewSet):
    """ViewSet for managing OnboardingImport instances."""

    permission_classes = [IsAuthenticated]
    serializer_class = OnboardingImportSerializer

    def get_queryset(self):
        return OnboardingImport.objects.filter(user=self.request.user).prefetch_related("image_files")

    def get_serializer_class(self):
        if self.action == 'create':
            return OnboardingImportCreateSerializer
        return super().get_serializer_class()

    def perform_create(self, serializer):
        import_instance = serializer.save()
        print(f"DEBUG: Created import instance with ID: {import_instance.id}")

        # Trigger async processing (for now, sync)
        service = AIOnboardingService()
        result = service.process_import(import_instance.id)
        print(f"DEBUG: Process result: {result}")

        # Update the instance with the result
        import_instance.refresh_from_db()
        print(f"DEBUG: Final instance status: {import_instance.status}, ID: {import_instance.id}")

        # Ensure the instance has an ID and is saved
        if not import_instance.id:
            import_instance.save()

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

    @action(detail=True, methods=['post'], url_path='create', url_name='create')
    def create_foodtruck(self, request, pk=None):
        """Create FoodTruck and related entities from a completed import."""
        import_instance = self.get_object()

        if import_instance.status != 'completed':
            return Response(
                {'error': 'Import is not yet processed.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        service = AIOnboardingService()
        try:
            result = service.create_foodtruck_from_import(import_instance)
            return Response(result, status=status.HTTP_201_CREATED)
        except ValidationError as exc:
            return Response({'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as exc:
            return Response({'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)


class GenerateFoodtruckView(generics.CreateAPIView):
    """Generate foodtruck with menu using AI."""
    permission_classes = [IsAuthenticated]
    serializer_class = GenerateFoodtruckSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        service = AIOnboardingService()
        result = service.generate_foodtruck(serializer.validated_data)

        return Response(result, status=status.HTTP_200_OK)
