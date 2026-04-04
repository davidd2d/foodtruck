from decimal import Decimal
from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.conf import settings
from django.utils import timezone
from django.utils.translation import gettext_lazy as _


class PickupSlot(models.Model):
    """
    Represents a pickup time slot for a food truck.

    Manages capacity and availability for order pickup.
    """
    food_truck = models.ForeignKey(
        'foodtrucks.FoodTruck',
        on_delete=models.CASCADE,
        related_name='pickup_slots',
        help_text=_("The food truck this slot belongs to")
    )
    start_time = models.DateTimeField(help_text=_("Start time of the pickup slot"))
    end_time = models.DateTimeField(help_text=_("End time of the pickup slot"))
    capacity = models.PositiveIntegerField(help_text=_("Maximum number of orders for this slot"))
    created_at = models.DateTimeField(auto_now_add=True, help_text=_("When the slot was created"))

    class Meta:
        verbose_name = _("Pickup Slot")
        verbose_name_plural = _("Pickup Slots")
        ordering = ['start_time']
        indexes = [
            models.Index(fields=['food_truck', 'start_time']),
        ]
        constraints = [
            models.CheckConstraint(
                check=models.Q(end_time__gt=models.F('start_time')),
                name='pickup_slot_end_after_start'
            ),
        ]

    def __str__(self):
        return f"{self.food_truck.name} - {self.start_time.strftime('%Y-%m-%d %H:%M')}"

    @property
    def current_orders_count(self):
        """Calculate current number of submitted orders for this slot."""
        return self.orders.filter(status__in=['submitted', 'paid']).count()

    def is_available(self):
        """Check if the slot has remaining capacity."""
        return self.current_orders_count < self.capacity

    def remaining_capacity(self):
        """Return the number of available spots in this slot."""
        return max(0, self.capacity - self.current_orders_count)

    def clean(self):
        """Validate that end_time is after start_time."""
        if self.end_time <= self.start_time:
            raise ValidationError("End time must be after start time")


class Order(models.Model):
    """
    Represents a customer order with items and pickup details.
    """

    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('submitted', 'Submitted'),
        ('paid', 'Paid'),
        ('cancelled', 'Cancelled'),
    ]

    customer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='orders',
        help_text=_("The customer who placed the order")
    )
    food_truck = models.ForeignKey(
        'foodtrucks.FoodTruck',
        on_delete=models.CASCADE,
        related_name='orders',
        help_text=_("The food truck for this order")
    )
    pickup_slot = models.ForeignKey(
        PickupSlot,
        on_delete=models.CASCADE,
        related_name='orders',
        help_text=_("The pickup slot for this order")
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='draft',
        help_text=_("Current status of the order")
    )
    total_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text=_("Total price of the order")
    )
    created_at = models.DateTimeField(auto_now_add=True, help_text=_("When the order was created"))

    class Meta:
        verbose_name = _("Order")
        verbose_name_plural = _("Orders")
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['pickup_slot']),
            models.Index(fields=['status']),
            models.Index(fields=['food_truck']),
        ]
        constraints = [
            models.CheckConstraint(
                check=models.Q(total_price__gte=0),
                name='order_total_price_non_negative'
            ),
        ]

    def __str__(self):
        return f"Order {self.id} - {self.customer.email}"

    def add_item(self, item, quantity, selected_options=None):
        """
        Add an item to the order.

        Args:
            item: menu.Item instance
            quantity: int, must be > 0
            selected_options: list of Option IDs

        Raises:
            ValidationError: If item is invalid or unavailable
        """
        if self.status != 'draft':
            raise ValidationError("Cannot modify order after submission")

        if not item.is_available:
            raise ValidationError(f"Item '{item.name}' is not available")

        if quantity <= 0:
            raise ValidationError("Quantity must be positive")

        # Validate options and calculate price
        unit_price = item.get_price_with_options(selected_options or [])

        # Create OrderItem
        order_item = OrderItem.objects.create(
            order=self,
            item=item,
            quantity=quantity,
            unit_price=unit_price,
            total_price=unit_price * quantity
        )

        # Create OrderItemOptions if any
        if selected_options:
            options = item.option_groups.prefetch_related('options').filter(
                options__id__in=selected_options
            ).values_list('options__id', 'options__price_modifier')

            for option_id, modifier in options:
                OrderItemOption.objects.create(
                    order_item=order_item,
                    option_id=option_id,
                    price_modifier=modifier
                )

        # Update total price
        self.total_price = self.calculate_total()
        self.save(update_fields=['total_price'])

    def calculate_total(self):
        """
        Calculate the total price from all order items.

        Returns:
            Decimal: Total price
        """
        return self.items.aggregate(
            total=models.Sum('total_price')
        )['total'] or Decimal('0.00')

    def can_be_submitted(self):
        """
        Check if the order can be submitted.

        Returns:
            bool: True if order can be submitted
        """
        return (
            self.status == 'draft' and
            self.items.exists() and
            self.total_price > 0 and
            self.pickup_slot.is_available() and
            self.food_truck.can_accept_orders()
        )

    @transaction.atomic
    def submit(self):
        """
        Submit the order, validating all constraints and reserving slot capacity.

        Raises:
            ValidationError: If order cannot be submitted
        """
        if not self.can_be_submitted():
            raise ValidationError("Order cannot be submitted")

        # Lock the pickup slot for update to prevent race conditions
        slot = PickupSlot.objects.select_for_update().get(id=self.pickup_slot_id)

        # Double-check availability after lock
        if not slot.is_available():
            raise ValidationError("Pickup slot is no longer available")

        # Update status
        self.status = 'submitted'
        self.save(update_fields=['status'])

    def is_paid(self):
        """
        Check if the order has been paid.

        Returns:
            bool: True if order has a successful payment
        """
        return hasattr(self, 'payment') and self.payment.status == 'paid'

    def mark_as_paid(self):
        """
        Mark the order as paid.

        This should only be called by the Payment model to maintain data integrity.
        Direct calls may break consistency.

        Raises:
            ValidationError: If order is not in correct state
        """
        if self.status != 'submitted':
            raise ValidationError(f"Cannot mark as paid from status '{self.status}'")

        self.status = 'paid'
        self.save(update_fields=['status'])

    def clean(self):
        """Validate order constraints."""
        if self.status != 'draft' and self.status != 'cancelled':
            # For submitted/paid orders, ensure all required data is present
            if not self.items.exists():
                raise ValidationError("Submitted orders must have items")


class OrderItem(models.Model):
    """
    Represents an item in an order with quantity and pricing snapshot.
    """
    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name='items',
        help_text=_("The order this item belongs to")
    )
    item = models.ForeignKey(
        'menu.Item',
        on_delete=models.CASCADE,
        help_text=_("The menu item")
    )
    quantity = models.PositiveIntegerField(help_text=_("Quantity ordered"))
    unit_price = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        help_text=_("Price per unit at time of order")
    )
    total_price = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        help_text=_("Total price for this item (unit_price * quantity)")
    )

    class Meta:
        verbose_name = _("Order Item")
        verbose_name_plural = _("Order Items")
        constraints = [
            models.CheckConstraint(
                check=models.Q(quantity__gt=0),
                name='order_item_quantity_positive'
            ),
            models.CheckConstraint(
                check=models.Q(unit_price__gte=0),
                name='order_item_unit_price_non_negative'
            ),
            models.CheckConstraint(
                check=models.Q(total_price__gte=0),
                name='order_item_total_price_non_negative'
            ),
        ]

    def __str__(self):
        return f"{self.item.name} x{self.quantity}"

    def save(self, *args, **kwargs):
        """Ensure total_price consistency."""
        if self.unit_price and self.quantity:
            self.total_price = self.unit_price * self.quantity
        super().save(*args, **kwargs)


class OrderItemOption(models.Model):
    """
    Represents a selected option for an order item with pricing snapshot.
    """
    order_item = models.ForeignKey(
        OrderItem,
        on_delete=models.CASCADE,
        related_name='selected_options',
        help_text=_("The order item this option belongs to")
    )
    option = models.ForeignKey(
        'menu.Option',
        on_delete=models.CASCADE,
        help_text=_("The selected option")
    )
    price_modifier = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        help_text=_("Price modifier at time of order")
    )

    class Meta:
        verbose_name = _("Order Item Option")
        verbose_name_plural = _("Order Item Options")
        constraints = [
            models.CheckConstraint(
                check=models.Q(price_modifier__gte=Decimal('-1000.00')),
                name='order_item_option_modifier_reasonable'
            ),
        ]

    def __str__(self):
        return f"{self.order_item} - {self.option.name}"
