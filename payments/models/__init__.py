from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import IntegrityError, models, transaction
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from common.services import AuditService


class Payment(models.Model):
    """Represents the Stripe Checkout payment state for one order."""

    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('paid', 'Paid'),
        ('failed', 'Failed'),
    ]

    order = models.OneToOneField(
        'orders.Order',
        on_delete=models.PROTECT,
        related_name='payment',
        help_text=_("The order this payment is for"),
    )
    provider = models.CharField(max_length=32, default='stripe', help_text=_("Payment provider"))
    stripe_session_id = models.CharField(max_length=255, unique=True)
    stripe_payment_intent = models.CharField(max_length=255, null=True, blank=True)
    stripe_connect_account_id = models.CharField(max_length=255, null=True, blank=True)
    transfer_group = models.CharField(max_length=255, null=True, blank=True)
    amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text=_("Payment amount"),
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending',
        help_text=_("Current payment status"),
    )
    paid_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, help_text=_("When the payment was created"))
    updated_at = models.DateTimeField(auto_now=True, help_text=_("When the payment was last updated"))

    class Meta:
        verbose_name = _("Payment")
        verbose_name_plural = _("Payments")
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status']),
            models.Index(fields=['paid_at']),
        ]
        constraints = [
            models.CheckConstraint(
                check=models.Q(amount__gt=0),
                name='payment_amount_positive',
            ),
        ]

    def __str__(self):
        return f"Payment for Order {self.order_id} - {self.amount}"

    def is_paid(self):
        return self.status == 'paid'

    @transaction.atomic
    def mark_as_paid(self, payment_intent_id=None):
        """Transition to paid and mark the linked order as paid exactly once."""
        if self.is_paid():
            return self

        self.order.freeze_financials()

        self.status = 'paid'
        self.paid_at = timezone.now()
        if payment_intent_id:
            self.stripe_payment_intent = payment_intent_id
            self.save(update_fields=['status', 'paid_at', 'stripe_payment_intent'])
        else:
            self.save(update_fields=['status', 'paid_at'])

        AuditService.log(
            'payment_success',
            self,
            payload={'order_id': self.order_id, 'provider': self.provider},
            user=self.order.user,
        )

        self.order.mark_as_paid()

        from orders.services.ticket_service import TicketService
        TicketService.generate_ticket(self.order)
        return self

    def mark_as_failed(self):
        """Move a non-paid payment to failed state."""
        if self.is_paid():
            raise ValidationError('Cannot fail an already paid payment.')
        if self.status == 'failed':
            return self

        self.status = 'failed'
        self.save(update_fields=['status'])
        return self

    def clean(self):
        """Validate payment data."""
        if self.amount <= Decimal('0.00'):
            raise ValidationError('Payment amount must be positive')


class StripeEvent(models.Model):
    """Stores processed Stripe events to enforce webhook idempotency."""

    stripe_event_id = models.CharField(max_length=255, unique=True)
    type = models.CharField(max_length=255)
    processed_at = models.DateTimeField(default=timezone.now)

    class Meta:
        verbose_name = _('Stripe Event')
        verbose_name_plural = _('Stripe Events')
        ordering = ['-processed_at']
        indexes = [
            models.Index(fields=['processed_at']),
        ]

    def __str__(self):
        return f"{self.type} ({self.stripe_event_id})"

    @classmethod
    def is_processed(cls, event_id):
        return cls.objects.filter(stripe_event_id=event_id).exists()

    @classmethod
    def mark_processed(cls, event_id, event_type):
        try:
            _, created = cls.objects.get_or_create(
                stripe_event_id=event_id,
                defaults={
                    'type': event_type,
                    'processed_at': timezone.now(),
                },
            )
            return created
        except IntegrityError:
            return False
