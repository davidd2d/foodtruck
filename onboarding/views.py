from django.shortcuts import render, get_object_or_404, redirect
from django.views.generic import TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import JsonResponse
from onboarding.models import OnboardingImport


class ImportView(LoginRequiredMixin, TemplateView):
    """View for the import form page."""
    template_name = 'onboarding/import.html'


class PreviewView(LoginRequiredMixin, TemplateView):
    """View for the preview and editing page."""
    template_name = 'onboarding/preview.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        import_id = kwargs.get('import_id')

        # Get the import instance
        import_instance = get_object_or_404(
            OnboardingImport,
            id=import_id,
            user=self.request.user
        )

        context['import_instance'] = import_instance
        context['import_data'] = import_instance.parsed_data or {}

        return context

    def get(self, request, *args, **kwargs):
        import_id = kwargs.get('import_id')
        import_instance = get_object_or_404(
            OnboardingImport,
            id=import_id,
            user=request.user
        )

        # Redirect to import if not completed
        if import_instance.status != 'completed':
            return redirect('onboarding:import')

        return super().get(request, *args, **kwargs)


# Keep the old view for backward compatibility
class AIOnboardingView(LoginRequiredMixin, TemplateView):
    template_name = 'onboarding/ai_input.html'
