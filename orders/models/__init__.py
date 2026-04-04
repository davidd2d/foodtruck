from decimal import Decimal
from django.core.exceptions import ValidationError
from django.db import models, transaction, OperationalError
from django.conf import settings
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from menu.models import Item, Option


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

    def _capacity_queryset(self, *, exclude_order=None, include_drafts=True):
        """Return the queryset used to evaluate slot capacity."""
        statuses = ['submitted', 'paid']
        if include_drafts:
            statuses.append('draft')
        qs = self.orders.filter(status__in=statuses)
        if exclude_order is not None:
            exclude_pk = exclude_order.pk if hasattr(exclude_order, 'pk') else exclude_order
            qs = qs.exclude(pk=exclude_pk)
        return qs

    @property
    def current_orders_count(self):
        """Count how many orders reserve this slot."""
        return self._capacity_queryset().count()

    def has_capacity_for(self, *, exclude_order=None, include_drafts=True):
        """Determine if there is room for another submitted order."""
        return self._capacity_queryset(
            exclude_order=exclude_order,
            include_drafts=include_drafts
        ).count() < self.capacity

    def is_available(self):
        """Check if the slot is in the future and has spare capacity."""
        return self.start_time >= timezone.now() and self.has_capacity_for()

    def remaining_capacity(self):
        """Return the number of spots remaining for booking."""
        return max(0, self.capacity - self.current_orders_count)

    @transaction.atomic
    def assign_order(self, order, *, include_drafts=True):
        """Assign a draft order to this slot while enforcing capacity and consistency."""

        slot = PickupSlot.objects.select_for_update().select_related('food_truck').get(pk=self.pk)

        if slot.food_truck_id != order.food_truck_id:
            raise ValidationError('Pickup slot must belong to the order food truck.')

        if slot.start_time < timezone.now():
            raise ValidationError('Pickup slot is in the past.')

        if not slot.has_capacity_for(exclude_order=order, include_drafts=include_drafts):
            raise ValidationError('Pickup slot is no longer available.')

        if order.status != 'draft':
            raise ValidationError('Only draft orders may be assigned to a pickup slot.')

        order.pickup_slot = slot
        order.save(update_fields=['pickup_slot'])
        return order

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
        null=True,
        blank=True,
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
    submitted_at = models.DateTimeField(null=True, blank=True, help_text=_("When the order was submitted"))

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

        if not item.is_available_now():
            raise ValidationError(f"Item '{item.name}' is not available")

        if quantity <= 0:
            raise ValidationError("Quantity must be positive")

        selected_options = selected_options or []
        item.validate_options(selected_options)

        # Calculate price and persist the order item
        unit_price = item.get_price_with_options(selected_options)

        order_item = OrderItem.objects.create(
            order=self,
            item=item,
            quantity=quantity,
            unit_price=unit_price,
            total_price=unit_price * quantity,
            options=[{'option_id': int(option_id)} for option_id in selected_options]
        )

        if selected_options:
            option_qs = Option.objects.filter(
                id__in=selected_options,
                group__item=item,
                is_available=True
            )
            for option in option_qs:
                OrderItemOption.objects.create(
                    order_item=order_item,
                    option=option,
                    price_modifier=option.price_modifier
                )

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

    def clear(self):
        """Remove all draft items from the order and reset totals."""
        if self.status != 'draft':
            raise ValidationError('Can only clear draft orders.')

        self.items.all().delete()
        self.total_price = Decimal('0.00')
        self.save(update_fields=['total_price'])

    def can_be_submitted(self):
        """Return True if the order satisfies submission criteria."""

        if self.status != 'draft':
            return False

        if not self.items.exists():
            return False

        if self.total_price <= Decimal('0.00'):
            return False

        if self.food_truck and not self.food_truck.can_accept_orders():
            return False

        slot = self.pickup_slot
        if not slot:
            return False

        if slot.start_time < timezone.now():
            return False

        if slot.food_truck_id != self.food_truck_id:
            return False

        if not slot.has_capacity_for(exclude_order=self, include_drafts=False):
            return False

        return all(
            order_item.item.is_available_now()
            for order_item in self.items.select_related('item')
        )

    def validate(self):
        """Raise ValidationError if the order cannot be submitted."""

        if self.status != 'draft':
            raise ValidationError('Only draft orders may be submitted.')

        if not self.items.exists():
            raise ValidationError('Order has no items.')

        if self.total_price <= Decimal('0.00'):
            raise ValidationError('Order total must be greater than zero.')

        if not self.food_truck.can_accept_orders():
            raise ValidationError('Food truck is not accepting orders at the moment.')

        slot = self.pickup_slot
        if not slot:
            raise ValidationError('Pickup slot must be selected before submission.')

        if slot.food_truck_id != self.food_truck_id:
            raise ValidationError('Pickup slot does not belong to this food truck.')

        if slot.start_time < timezone.now():
            raise ValidationError('Pickup slot is in the past.')

        if not slot.has_capacity_for(exclude_order=self, include_drafts=False):
            raise ValidationError('Pickup slot is no longer available.')

        invalid_items = []
        for order_item in self.items.select_related('item__category__menu__food_truck'):
            item = order_item.item
            if not item.is_available_now():
                invalid_items.append(item.name)
            elif item.category.menu.food_truck_id != self.food_truck_id:
                raise ValidationError('Order contains items from multiple food trucks.')

        if invalid_items:
            message = ', '.join(invalid_items)
            raise ValidationError(f"Items not available: {message}")

    @transaction.atomic
    def submit(self):
        """Atomically validate the order and reserve the pickup slot."""

        try:
            self.validate()

            slot = PickupSlot.objects.select_for_update().get(pk=self.pickup_slot_id)
            slot.assign_order(self, include_drafts=False)

            self.status = 'submitted'
            self.submitted_at = timezone.now()
            self.save(update_fields=['status', 'submitted_at'])
        except OperationalError:
            raise ValidationError('Pickup slot is no longer available.')

    def is_paid(self):
        """
        Check if the order has been paid.

        Returns:
            bool: True if order has a successful payment
        """
        return hasattr(self, 'payment') and self.payment.is_paid()

    def mark_as_paid(self):
        """
        Mark the order as paid.

        This should only be called by the Payment model to maintain data integrity.
        Direct calls may break consistency.

        Raises:
            ValidationError: If order is not in correct state
        """
        if self.status == 'paid':
            raise ValidationError('Order is already marked as paid.')

        if self.status != 'submitted':
            raise ValidationError(f"Cannot mark as paid from status '{self.status}'")

        if not hasattr(self, 'payment'):
            raise ValidationError('Order has no associated payment.')

        if not self.payment.is_paid():
            raise ValidationError('Payment must be paid before marking order as paid.')

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
    options = models.JSONField(
        default=list,
        blank=True,
        help_text=_("Selected item options snapshot")
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
