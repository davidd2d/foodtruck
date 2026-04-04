from decimal import Decimal
from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.utils import timezone
from django.utils.translation import gettext_lazy as _


class Payment(models.Model):
    """
    Represents a payment for an order.

    Handles payment lifecycle and integration with external payment providers.
    Designed to be extensible for multiple payment providers.
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

    def initialize(self):
        """
        Initialize the payment for a submitted order.

        Sets status to pending and copies amount from order.
        Should be called when starting the payment process.

        Raises:
            ValidationError: If order is not in correct state or payment already exists
        """
        if hasattr(self.order, 'payment') and self.order.payment != self:
            raise ValidationError("Order already has a payment")

        if self.order.status != 'submitted':
            raise ValidationError("Can only create payment for submitted orders")

        self.amount = self.order.total_price
        self.status = 'pending'
        self.save()

    def mark_as_authorized(self, provider_id=None):
        """
        Mark the payment as authorized by the payment provider.

        Args:
            provider_id: Optional provider payment ID

        Raises:
            ValidationError: If current status doesn't allow authorization
        """
        if self.status not in ['pending']:
            raise ValidationError(f"Cannot authorize payment with status '{self.status}'")

        if provider_id:
            self.provider_payment_id = provider_id

        self.status = 'authorized'
        self.save(update_fields=['status', 'provider_payment_id', 'updated_at'])

    def mark_as_paid(self):
        """
        Mark the payment as successfully paid.

        Updates payment status and related order status.
        Should only be called after successful payment confirmation.

        Raises:
            ValidationError: If current status doesn't allow payment
        """
        if self.status not in ['pending', 'authorized']:
            raise ValidationError(f"Cannot mark as paid from status '{self.status}'")

        with transaction.atomic():
            self.status = 'paid'
            self.save(update_fields=['status', 'updated_at'])

            # Update order status
            self.order.mark_as_paid()

    def mark_as_failed(self):
        """
        Mark the payment as failed.

        Should be called when payment processing fails.
        """
        self.status = 'failed'
        self.save(update_fields=['status', 'updated_at'])

    def refund(self):
        """
        Process a refund for the payment.

        Only allowed for paid payments.

        Raises:
            ValidationError: If payment cannot be refunded
        """
        if self.status != 'paid':
            raise ValidationError(f"Cannot refund payment with status '{self.status}'")

        self.status = 'refunded'
        self.save(update_fields=['status', 'updated_at'])

    def can_be_refunded(self):
        """
        Check if the payment can be refunded.

        Returns:
            bool: True if refund is possible
        """
        return self.status == 'paid'

    def clean(self):
        """Validate payment data."""
        if self.amount <= 0:
            raise ValidationError("Payment amount must be positive")

        if self.currency and len(self.currency) != 3:
            raise ValidationError("Currency must be a 3-letter code")
