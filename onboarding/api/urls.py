from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r'imports', views.OnboardingImportViewSet, basename='onboarding-import')

urlpatterns = [
    path('', include(router.urls)),
]