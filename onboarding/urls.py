from django.urls import path
from . import views

app_name = 'onboarding'

urlpatterns = [
    path('import/', views.ImportView.as_view(), name='import'),
    path('preview/<int:import_id>/', views.PreviewView.as_view(), name='preview'),
    path('ai/', views.AIOnboardingView.as_view(), name='ai-input'),  # Keep for backward compatibility
]