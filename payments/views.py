from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.views.generic import TemplateView

from orders.models import Order


class PaymentPageView(LoginRequiredMixin, TemplateView):
    """Render the payment page for a submitted order."""

    template_name = 'payments/checkout.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        order = get_object_or_404(
            Order.objects.select_related('pickup_slot', 'food_truck').prefetch_related('items'),
            pk=self.kwargs['order_id'],
            user=self.request.user,
            payment_method=Order.PaymentMethod.ONLINE,
            food_truck__slug=self.kwargs['slug'],
        )
        context.update({
            'order': order,
            'success_url': reverse('payments:success', kwargs={'slug': order.food_truck.slug, 'order_id': order.id}),
        })
        return context


class PaymentSuccessView(LoginRequiredMixin, TemplateView):
    """Simple confirmation page displayed after a successful payment."""

    template_name = 'payments/success.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        order = Order.objects.filter(
            pk=self.kwargs['order_id'],
            user=self.request.user,
            paid_at__isnull=False,
            food_truck__slug=self.kwargs['slug'],
        ).select_related('food_truck', 'ticket').first()

        context.update({
            'order': order,
        })
        return context
