from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction

from orders.models import Order
from payments.models import Payment


class PaymentService:
    """Service orchestrating the simulated payment lifecycle."""

    @staticmethod
    def create_payment(order: Order) -> Payment:
        """Create a pending payment for a submitted order."""

        if order.status != 'submitted':
            raise ValidationError('Only submitted orders can be paid.')

        if not order.items.exists():
            raise ValidationError('Cannot pay for an empty order.')

        if order.is_paid():
            raise ValidationError('Order is already paid.')

        if hasattr(order, 'payment'):
            raise ValidationError('Payment already exists for this order.')

        total = order.calculate_total()
        if total <= Decimal('0.00'):
            raise ValidationError('Order total must be greater than zero.')

        return Payment.objects.create(
            order=order,
            amount=total,
            status='pending',
        )

    @staticmethod
    def authorize_payment(payment: Payment) -> Payment:
        """Simulate provider authorization for a pending payment."""

        payment.transition_to('authorized')
        return payment

    @staticmethod
    def capture_payment(payment: Payment) -> Payment:
        """Simulate capture and mark both payment and order as paid."""

        if payment.order.is_paid():
            raise ValidationError('Order has already been marked as paid.')

        with transaction.atomic():
            payment.transition_to('paid')
            payment.order.mark_as_paid()

        return payment

    @staticmethod
    def fail_payment(payment: Payment) -> Payment:
        """Bring a payment into the failed state."""

        payment.transition_to('failed')
        return payment
