from decimal import Decimal
import uuid

from django.core.exceptions import ValidationError
from django.db import transaction

from orders.models import Order
from payments.models import Payment


class PaymentService:
    """Service orchestrating the simulated payment lifecycle."""

    @staticmethod
    def create_payment(order: Order) -> Payment:
        """Create a pending payment for a submitted order."""

        if order.payment_method != Order.PaymentMethod.ONLINE:
            raise ValidationError('Only online-payment orders can create a payment session.')

        if order.status != Order.Status.PENDING:
            raise ValidationError('Only pending orders can be paid.')

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
            stripe_session_id=f'sim_{uuid.uuid4().hex}',
            stripe_connect_account_id=order.food_truck.stripe_connect_account_id,
            transfer_group=f'order_{order.id}',
        )

    @staticmethod
    def authorize_payment(payment: Payment) -> Payment:
        """Legacy no-op endpoint retained for backward compatibility."""
        if payment.status != 'pending':
            raise ValidationError('Only pending payments can remain authorized for checkout.')
        return payment

    @staticmethod
    def capture_payment(payment: Payment) -> Payment:
        """Capture funds and mark payment/order as paid."""

        if payment.order.is_paid():
            raise ValidationError('Order has already been marked as paid.')

        with transaction.atomic():
            payment.mark_as_paid(payment_intent_id=payment.stripe_payment_intent)

        return payment

    @staticmethod
    def fail_payment(payment: Payment) -> Payment:
        """Bring a payment into the failed state."""

        payment.mark_as_failed()
        return payment
