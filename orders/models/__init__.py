
# -*- coding: utf-8 -*-
from datetime import timedelta
from decimal import Decimal
import math
from typing import Optional

import pytz

from django.core.exceptions import ValidationError
from django.db import models, transaction, OperationalError
from django.conf import settings
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from menu.models import Combo, Item, Option

PARIS_TZ = pytz.timezone('Europe/Paris')


class ServiceSchedule(models.Model):
    """
    Defines the recurring working windows for a food truck.
    """
    DAY_CHOICES = [
        (0, _("Monday")),
        (1, _("Tuesday")),
        (2, _("Wednesday")),
        (3, _("Thursday")),
        (4, _("Friday")),
        (5, _("Saturday")),
        (6, _("Sunday")),
    ]

    food_truck = models.ForeignKey(
        'foodtrucks.FoodTruck',
        on_delete=models.CASCADE,
        related_name='service_schedules',
        help_text=_("The food truck this schedule belongs to")
    )
    day_of_week = models.IntegerField(choices=DAY_CHOICES, help_text=_("Day of week (0=Monday)"))
    start_time = models.TimeField(help_text=_("Window start time"))
    end_time = models.TimeField(help_text=_("Window end time"))
    capacity_per_slot = models.PositiveIntegerField(help_text=_("Capacity per generated slot"))
    slot_duration_minutes = models.PositiveIntegerField(default=10, help_text=_("Duration of each slot in minutes"))
    is_active = models.BooleanField(default=True, help_text=_("Whether this schedule is currently active"))
    location = models.ForeignKey(
        'Location',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='service_schedules',
        help_text=_('Optional location this schedule takes place at')
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("Service Schedule")
        verbose_name_plural = _("Service Schedules")
        ordering = ['food_truck', 'day_of_week', 'start_time']
        constraints = [
            models.UniqueConstraint(
                fields=['food_truck', 'day_of_week', 'start_time', 'end_time'],
                name='unique_service_schedule_window'
            ),
        ]

    def get_effective_location(self):
        if self.has_custom_location():
            return self.location
        return self.food_truck

    def has_custom_location(self) -> bool:
        return self.location is not None and self.location.is_active

    def clean(self):
        if self.end_time <= self.start_time:
            raise ValidationError(_("Schedule end time must be after start time."))

        overlapping = ServiceSchedule.objects.filter(
            food_truck=self.food_truck,
            day_of_week=self.day_of_week,
            is_active=True
        )
        if self.pk:
            overlapping = overlapping.exclude(pk=self.pk)

        for other in overlapping:
            if (self.start_time < other.end_time) and (self.end_time > other.start_time):
                raise ValidationError(_("This schedule overlaps with another window on the same day."))

        if self.location and self.location.food_truck_id != self.food_truck_id:
            raise ValidationError(_("Selected location must belong to this food truck."))


class Location(models.Model):
    """Represents a defined pickup location owned by a food truck."""

    food_truck = models.ForeignKey(
        'foodtrucks.FoodTruck',
        on_delete=models.CASCADE,
        related_name='locations',
        help_text=_('Food truck this location belongs to')
    )
    name = models.CharField(max_length=200, blank=True, help_text=_('Optional spot name'))
    address_line_1 = models.CharField(max_length=255, blank=True, help_text=_('Street address'))
    address_line_2 = models.CharField(max_length=255, blank=True, null=True)
    postal_code = models.CharField(max_length=20, help_text=_('Postal / ZIP code'))
    city = models.CharField(max_length=100, help_text=_('City'))
    country = models.CharField(max_length=100, help_text=_('Country'))
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True, db_index=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True, db_index=True)
    notes = models.TextField(blank=True, help_text=_('Pickup instructions'))
    is_active = models.BooleanField(default=True, help_text=_('Whether this location is currently in use'))
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _('Location')
        verbose_name_plural = _('Locations')
        indexes = [
            models.Index(fields=['food_truck']),
            models.Index(fields=['latitude', 'longitude']),
        ]
        constraints = [
            models.CheckConstraint(
                check=models.Q(latitude__gte=-90, latitude__lte=90, longitude__gte=-180, longitude__lte=180),
                name='location_valid_coordinates'
            ),
        ]

    def __str__(self):
        if self.name:
            return self.name
        return f"{self.city} ({self.postal_code})"

    def clean(self):
        if hasattr(self, 'latitude') and self.latitude is not None and hasattr(self, 'longitude') and self.longitude is not None:
            lat = float(self.latitude)
            lng = float(self.longitude)
            if not (-90 <= lat <= 90):
                raise ValidationError(_('Latitude must be between -90 and 90.'))
            if not (-180 <= lng <= 180):
                raise ValidationError(_('Longitude must be between -180 and 180.'))
        if not self.has_address() and not self.has_coordinates():
            raise ValidationError(_('Provide either an address or GPS coordinates.'))

    def get_full_address(self) -> str:
        parts = [self.address_line_1]
        if self.address_line_2:
            parts.append(self.address_line_2)
        parts.append(f"{self.postal_code} {self.city}")
        parts.append(self.country)
        return ', '.join(part for part in parts if part)

    def get_coordinates(self) -> tuple:
        return (float(self.latitude), float(self.longitude))

    def distance_to(self, lat: float, lng: float) -> float:
        return _haversine_distance(*self.get_coordinates(), float(lat), float(lng))

    def is_same_as_base_location(self) -> bool:
        if not hasattr(self.food_truck, 'latitude') or not hasattr(self.food_truck, 'longitude'):
            return False
        base_lat = float(self.food_truck.latitude)
        base_lng = float(self.food_truck.longitude)
        lat, lng = self.get_coordinates()
        return math.isclose(base_lat, lat, abs_tol=1e-6) and math.isclose(base_lng, lng, abs_tol=1e-6)

    def has_address(self) -> bool:
        return bool(self.address_line_1)

    def has_coordinates(self) -> bool:
        return self.latitude is not None and self.longitude is not None


def _haversine_distance(lat1, lng1, lat2, lng2):
    R = 6371
    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)
    delta_lat = math.radians(lat2 - lat1)
    delta_lng = math.radians(lng2 - lng1)
    a = math.sin(delta_lat / 2) ** 2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lng / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c

class PickupSlotQuerySet(models.QuerySet):
    """QuerySet helpers for pickup slots."""

    def upcoming_for(self, food_truck):
        """Return slots for the food truck that start in the Paris timezone future."""
        paris_now = timezone.localtime(timezone.now(), PARIS_TZ)
        return self.filter(
            food_truck=food_truck,
            end_time__gt=paris_now,
        ).order_by('start_time')


class PickupSlotManager(models.Manager):
    """Manager that exposes slot helpers."""

    def get_queryset(self):
        return PickupSlotQuerySet(self.model, using=self._db).select_related('food_truck')

    def upcoming_for(self, food_truck):
        return self.get_queryset().upcoming_for(food_truck)


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
    service_schedule = models.ForeignKey(
        'ServiceSchedule',
        on_delete=models.SET_NULL,
        related_name='pickup_slots',
        null=True,
        blank=True,
        help_text=_("Originating service schedule, if any"),
    )
    created_at = models.DateTimeField(auto_now_add=True, help_text=_("When the slot was created"))
    updated_at = models.DateTimeField(auto_now=True, help_text=_("When the slot was last updated"))

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

    objects = PickupSlotManager()

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

    @property
    def current_bookings(self):
        """Alias for current reservations (used on the frontend)."""
        return self.current_orders_count

    def has_capacity_for(self, *, exclude_order=None, include_drafts=True):
        """Determine if there is room for another submitted order."""
        return self._capacity_queryset(
            exclude_order=exclude_order,
            include_drafts=include_drafts
        ).count() < self.capacity

    def is_available(self):
        """Check if the slot is in the future and has spare capacity."""
        paris_now = timezone.localtime(timezone.now(), PARIS_TZ)
        return self.start_time >= paris_now and self.has_capacity_for()

    def remaining_capacity(self):
        """Return the number of spots remaining for booking."""
        return max(0, self.capacity - self.current_orders_count)

    @transaction.atomic
    def assign_order(self, order, *, include_drafts=True):
        """Assign a draft order to this slot while enforcing capacity and consistency."""

        slot = PickupSlot.objects.select_for_update().select_related('food_truck').get(pk=self.pk)

        if slot.food_truck_id != order.food_truck_id:
            raise ValidationError('Pickup slot must belong to the order food truck.')

        paris_now = timezone.localtime(timezone.now(), PARIS_TZ)
        if slot.start_time <= paris_now:
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
    Represents an authenticated order with pickup details and lifecycle management.
    """

    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('submitted', 'Submitted'),
        ('paid', 'Paid'),
        ('cancelled', 'Cancelled'),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='orders',
        null=True,
        blank=True,
        help_text=_("The account that placed or owns this order")
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
        owner_email = getattr(self.user, 'email', 'anonymous')
        return f"Order {self.id} - {owner_email}"

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

    def add_combo(self, combo, quantity):
        """Add a combo to the order as a priced snapshot line."""
        if self.status != 'draft':
            raise ValidationError("Cannot modify order after submission")

        if combo.category.menu.food_truck_id != self.food_truck_id:
            raise ValidationError('Combo belongs to another food truck')

        if not combo.is_available:
            raise ValidationError(f"Combo '{combo.name}' is not available")

        if quantity <= 0:
            raise ValidationError("Quantity must be positive")

        unit_price = combo.get_effective_price()
        if unit_price is None:
            raise ValidationError(f"Combo '{combo.name}' needs a confirmed price before ordering")

        OrderItem.objects.create(
            order=self,
            combo=combo,
            quantity=quantity,
            unit_price=unit_price,
            total_price=unit_price * quantity,
            options=[],
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
        """Return True when the draft order meets all submission requirements."""

        if self.status != 'draft':
            return False

        if not self.items.exists():
            return False

        if self.total_price <= Decimal('0.00'):
            return False

        if not self.food_truck or not self.food_truck.can_accept_orders():
            return False

        slot = self.pickup_slot
        if not slot:
            return False

        if slot.food_truck_id != self.food_truck_id:
            return False

        now = timezone.localtime(timezone.now(), PARIS_TZ)
        if slot.start_time <= now:
            return False

        if not slot.has_capacity_for(exclude_order=self, include_drafts=False):
            return False

        for order_item in self.items.select_related(
            'item__category__menu__food_truck',
            'combo__category__menu__food_truck',
        ):
            if order_item.item_id:
                item = order_item.item
                if not item.is_available_now() or item.category.menu.food_truck_id != self.food_truck_id:
                    return False
                continue

            combo = order_item.combo
            if not combo or not combo.is_available or combo.category.menu.food_truck_id != self.food_truck_id:
                return False
            if combo.get_effective_price() is None:
                return False

        return True

    def validate(self):
        """Raise ValidationError when business rules forbid submission."""

        if self.status != 'draft':
            raise ValidationError('Only draft orders may be submitted.')

        if not self.items.exists():
            raise ValidationError('Order has no items.')

        if self.total_price <= Decimal('0.00'):
            raise ValidationError('Order total must be greater than zero.')

        if not self.food_truck or not self.food_truck.can_accept_orders():
            raise ValidationError('Food truck is not accepting orders at the moment.')

        slot = self.pickup_slot
        if not slot:
            raise ValidationError('Pickup slot must be selected before submission.')

        if slot.food_truck_id != self.food_truck_id:
            raise ValidationError('Pickup slot does not belong to this food truck.')

        now = timezone.localtime(timezone.now(), PARIS_TZ)
        if slot.start_time <= now:
            raise ValidationError('Pickup slot is in the past.')

        if not slot.has_capacity_for(exclude_order=self, include_drafts=False):
            raise ValidationError('Pickup slot is no longer available.')

        invalid_items = []
        for order_item in self.items.select_related(
            'item__category__menu__food_truck',
            'combo__category__menu__food_truck',
        ):
            if order_item.item_id:
                item = order_item.item
                if not item.is_available_now():
                    invalid_items.append(item.name)
                elif item.category.menu.food_truck_id != self.food_truck_id:
                    raise ValidationError('Order contains items from multiple food trucks.')
                continue

            combo = order_item.combo
            if not combo or not combo.is_available:
                invalid_items.append(getattr(combo, 'name', 'Combo'))
            elif combo.category.menu.food_truck_id != self.food_truck_id:
                raise ValidationError('Order contains items from multiple food trucks.')
            elif combo.get_effective_price() is None:
                invalid_items.append(combo.name)

        if invalid_items:
            message = ', '.join(invalid_items)
            raise ValidationError(f"Items not available: {message}")

    @transaction.atomic
    def submit(self):
        """Atomically validate and reserve the pickup slot."""

        try:
            self.validate()

            if self.status != 'draft':
                raise ValidationError('Only draft orders may be submitted.')

            if not self.pickup_slot_id:
                raise ValidationError('Pickup slot must be selected before submission.')

            try:
                slot = PickupSlot.objects.select_for_update().select_related('food_truck').get(
                    pk=self.pickup_slot_id
                )
            except PickupSlot.DoesNotExist:
                raise ValidationError('Pickup slot does not exist.')

            if slot.food_truck_id != self.food_truck_id:
                raise ValidationError('Pickup slot does not belong to this food truck.')

            now = timezone.localtime(timezone.now(), PARIS_TZ)
            if slot.start_time <= now:
                raise ValidationError('Pickup slot is in the past.')

            if not slot.has_capacity_for(exclude_order=self, include_drafts=False):
                raise ValidationError('Pickup slot is no longer available.')

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
        null=True,
        blank=True,
        help_text=_("The menu item")
    )
    combo = models.ForeignKey(
        'menu.Combo',
        on_delete=models.CASCADE,
        related_name='order_items',
        null=True,
        blank=True,
        help_text=_("The menu combo")
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
                check=(
                    (models.Q(item__isnull=False) & models.Q(combo__isnull=True)) |
                    (models.Q(item__isnull=True) & models.Q(combo__isnull=False))
                ),
                name='order_item_exactly_one_product'
            ),
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
        return f"{self.product_name} x{self.quantity}"

    @property
    def line_type(self):
        return 'combo' if self.combo_id else 'item'

    @property
    def product_name(self):
        if self.item_id:
            return self.item.name
        if self.combo_id:
            return self.combo.name
        return 'Unknown product'

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
