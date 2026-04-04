from decimal import Decimal
from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.utils.translation import gettext_lazy as _


class Payment(models.Model):
    """
    Represents a payment for a submitted order.

    Tracks the lifecycle of a payment with strictly enforced transitions
    so that the state machine can stay in sync with order status.
    """

    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('authorized', 'Authorized'),
        ('paid', 'Paid'),
        ('failed', 'Failed'),
        ('refunded', 'Refunded'),
    ]

    PROVIDER_CHOICES = [
        ('stripe', 'Stripe'),
        ('paypal', 'PayPal'),
        ('bank_transfer', 'Bank Transfer'),
    ]

    STATUS_TRANSITIONS = {
        'pending': {'authorized'},
        'authorized': {'paid', 'failed'},
        'paid': {'refunded'},
    }

    order = models.OneToOneField(
        'orders.Order',
        on_delete=models.CASCADE,
        related_name='payment',
        help_text=_("The order this payment is for")
    )
    amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text=_("Payment amount")
    )
    currency = models.CharField(
        max_length=3,
        default='EUR',
        help_text=_("Currency code (ISO 4217)")
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending',
        help_text=_("Current payment status")
    )
    provider = models.CharField(
        max_length=50,
        choices=PROVIDER_CHOICES,
        default='stripe',
        help_text=_("Payment provider")
    )
    provider_payment_id = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        help_text=_("Payment ID from the provider")
    )
    created_at = models.DateTimeField(auto_now_add=True, help_text=_("When the payment was created"))
    updated_at = models.DateTimeField(auto_now=True, help_text=_("When the payment was last updated"))

    class Meta:
        verbose_name = _("Payment")
        verbose_name_plural = _("Payments")
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status']),
            models.Index(fields=['provider_payment_id']),
        ]
        constraints = [
            models.CheckConstraint(
                check=models.Q(amount__gt=0),
                name='payment_amount_positive'
            ),
        ]

    def __str__(self):
        return f"Payment for Order {self.order_id} - {self.amount} {self.currency}"

    def is_paid(self):
        """Return True when the payment reached the paid state."""
        return self.status == 'paid'

    def can_transition_to(self, new_status):
        """Determine whether transitioning to the provided status is allowed."""
        if not isinstance(new_status, str):
            return False
        allowed = self.STATUS_TRANSITIONS.get(self.status, set())
        return new_status in allowed

    def transition_to(self, new_status, *, provider_payment_id=None):
        """
        Transition the payment status through the defined state machine.

        The transition is transactional so that the payment cannot land in an
        intermediate state if saving fails.
        """
        new_status = new_status.lower()

        if new_status == self.status:
            raise ValidationError(f"Payment already in '{self.status}' state")

        if not self.can_transition_to(new_status):
            raise ValidationError(f"Cannot transition from '{self.status}' to '{new_status}'")

        with transaction.atomic():
            self.status = new_status
            update_fields = ['status', 'updated_at']
            if provider_payment_id is not None:
                self.provider_payment_id = provider_payment_id
                update_fields.append('provider_payment_id')
            self.save(update_fields=update_fields)

    def clean(self):
        """Validate payment data."""
        if self.amount <= Decimal('0.00'):
            raise ValidationError("Payment amount must be positive")

        if self.currency and len(self.currency) != 3:
            raise ValidationError("Currency must be a 3-letter code")
