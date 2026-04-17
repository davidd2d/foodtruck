import stripe

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import transaction

from payments.models import Payment, StripeEvent
from payments.services.stripe_connect_service import StripeConnectService


class StripeWebhookService:
    """Handle Stripe webhooks with strict signature verification and idempotency."""

    @staticmethod
    def construct_event(payload, sig_header):
        """Validate Stripe signature and return the parsed event."""
        webhook_secret = getattr(settings, 'STRIPE_WEBHOOK_SECRET', None)
        if not webhook_secret:
            raise ValidationError('STRIPE_WEBHOOK_SECRET is not configured.')

        return stripe.Webhook.construct_event(payload, sig_header, webhook_secret)

    @classmethod
    def handle_event(cls, event):
        """Route an event after checking idempotency."""
        event_id = event.get('id')
        event_type = event.get('type')

        if not event_id or not event_type:
            raise ValidationError('Invalid Stripe event payload.')

        if StripeEvent.is_processed(event_id):
            return False

        with transaction.atomic():
            if StripeEvent.is_processed(event_id):
                return False

            if event_type == 'checkout.session.completed':
                cls.handle_checkout_completed(event)
            elif event_type == 'account.updated':
                StripeConnectService.handle_account_updated(event)

            StripeEvent.mark_processed(event_id, event_type)

        return True

    @staticmethod
    def handle_checkout_completed(event):
        """Mark payment and order as paid from a completed Checkout session."""
        session = (event.get('data') or {}).get('object') or {}
        session_id = session.get('id')
        payment_intent_id = session.get('payment_intent')
        metadata = session.get('metadata') or {}
        order_id = metadata.get('order_id')

        if not session_id:
            raise ValidationError('Missing Stripe session id in webhook event.')

        payment = Payment.objects.select_related('order').filter(stripe_session_id=session_id).first()
        if not payment:
            raise ValidationError('Payment not found for Stripe session.')

        if order_id and str(payment.order_id) != str(order_id):
            raise ValidationError('Stripe metadata order_id does not match payment order.')

        payment.mark_as_paid(payment_intent_id=payment_intent_id)
        return payment
