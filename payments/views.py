from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404
from django.urls import reverse_lazy
from django.views.generic import TemplateView

from orders.models import Order


class PaymentPageView(LoginRequiredMixin, TemplateView):
    """Render the payment page for a submitted order."""

    template_name = 'payments/checkout.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        order = get_object_or_404(
            Order.objects.select_related('pickup_slot').prefetch_related('items'),
            pk=self.kwargs['order_id'],
            customer=self.request.user
        )
        context.update({
            'order': order,
            'success_url': reverse_lazy('payments:success'),
        })
        return context


class PaymentSuccessView(LoginRequiredMixin, TemplateView):
    """Simple confirmation page displayed after a successful payment."""

    template_name = 'payments/success.html'
