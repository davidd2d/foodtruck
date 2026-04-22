
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
from common.services import AuditService
from menu.models import Combo, Item, Option
from orders.exceptions import OrderTransitionError

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

    def resolve_geodata(self, geocoding_service=None):
        """Fill missing address or coordinates from the available location data."""
        if self.has_address() and self.has_coordinates():
            return self

        if geocoding_service is None:
            from orders.services.location_geocoding_service import LocationGeocodingService
            geocoding_service = LocationGeocodingService

        if self.has_address() and not self.has_coordinates():
            latitude, longitude = geocoding_service.geocode_address(self.get_full_address())
            self.latitude = latitude
            self.longitude = longitude
            return self

        if self.has_coordinates() and not self.has_address():
            resolved = geocoding_service.reverse_geocode(float(self.latitude), float(self.longitude))
            self.address_line_1 = resolved.get('address_line_1', self.address_line_1)
            self.address_line_2 = resolved.get('address_line_2', self.address_line_2)
            self.postal_code = resolved.get('postal_code', self.postal_code)
            self.city = resolved.get('city', self.city)
            self.country = resolved.get('country', self.country)
            return self

        return self


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
        statuses = list(Order.capacity_reserved_statuses(include_drafts=False))
        if include_drafts:
            statuses.append(Order.Status.DRAFT)
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

    class Status(models.TextChoices):
        DRAFT = 'draft', _('Draft')
        PENDING = 'pending', _('Pending')
        CONFIRMED = 'confirmed', _('Confirmed')
        PREPARING = 'preparing', _('Preparing')
        READY = 'ready', _('Ready')
        COMPLETED = 'completed', _('Completed')
        CANCELLED = 'cancelled', _('Cancelled')

    STATUS_TRANSITIONS = {
        Status.PENDING: {Status.CONFIRMED, Status.CANCELLED},
        Status.CONFIRMED: {Status.PREPARING, Status.CANCELLED},
        Status.PREPARING: {Status.READY},
        Status.READY: {Status.COMPLETED},
    }

    DASHBOARD_STATUSES = (
        Status.PENDING,
        Status.CONFIRMED,
        Status.PREPARING,
        Status.READY,
        Status.COMPLETED,
    )

    ACTIVE_STATUSES = (
        Status.PENDING,
        Status.CONFIRMED,
        Status.PREPARING,
        Status.READY,
    )

    LEGACY_SUBMITTED_STATUS = 'submitted'

    class OrderQuerySet(models.QuerySet):
        """Query helpers for order retrieval in customer and operator contexts."""

        def for_dashboard(self, foodtruck, include_cancelled=False):
            queryset = self.filter(food_truck=foodtruck).select_related('pickup_slot').prefetch_related(
                'items',
                'items__item',
                'items__combo',
                'items__selected_options__option',
            )
            if not include_cancelled:
                queryset = queryset.exclude(status=Order.Status.CANCELLED)
            return queryset.order_by('pickup_slot__start_time', 'created_at')

        def by_status(self, status):
            return self.filter(status=status)

        def upcoming(self):
            return self.filter(pickup_slot__start_time__date__gte=timezone.localdate()).select_related('pickup_slot')

        def active(self):
            return self.exclude(status__in=[Order.Status.DRAFT, Order.Status.COMPLETED, Order.Status.CANCELLED])

    class OrderManager(models.Manager):
        """Manager exposing optimized dashboard-ready query helpers."""

        def get_queryset(self):
            return Order.OrderQuerySet(self.model, using=self._db)

        def for_dashboard(self, foodtruck, include_cancelled=False):
            return self.get_queryset().for_dashboard(foodtruck, include_cancelled=include_cancelled)

        def by_status(self, status):
            return self.get_queryset().by_status(status)

        def upcoming(self):
            return self.get_queryset().upcoming()

        def active(self):
            return self.get_queryset().active()

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
        choices=Status.choices,
        default=Status.DRAFT,
        help_text=_("Current status of the order")
    )
    customer_name = models.CharField(max_length=255, blank=True, default='')
    customer_email = models.EmailField(null=True, blank=True)
    customer_phone = models.CharField(max_length=32, null=True, blank=True)
    is_anonymized = models.BooleanField(default=False)
    total_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text=_("Total price of the order")
    )
    total_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text=_("Frozen financial total amount")
    )
    tax_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text=_("Frozen total tax amount")
    )
    currency = models.CharField(max_length=3, default='EUR', help_text=_("ISO 4217 currency code"))
    created_at = models.DateTimeField(auto_now_add=True, help_text=_("When the order was created"))
    submitted_at = models.DateTimeField(null=True, blank=True, help_text=_("When the order was submitted"))
    paid_at = models.DateTimeField(null=True, blank=True, help_text=_("When the order was paid"))
    anonymized_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = _("Order")
        verbose_name_plural = _("Orders")
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['pickup_slot']),
            models.Index(fields=['status']),
            models.Index(fields=['created_at']),
            models.Index(fields=['food_truck']),
            models.Index(fields=['paid_at']),
        ]
        constraints = [
            models.CheckConstraint(
                check=models.Q(total_price__gte=0),
                name='order_total_price_non_negative'
            ),
            models.CheckConstraint(
                check=models.Q(total_amount__gte=0),
                name='order_total_amount_non_negative'
            ),
            models.CheckConstraint(
                check=models.Q(tax_amount__gte=0),
                name='order_tax_amount_non_negative'
            ),
        ]

    objects = OrderManager()

    def __str__(self):
        owner_email = getattr(self.user, 'email', 'anonymous')
        return f"Order {self.id} - {owner_email}"

    def snapshot_customer_data(self):
        if not self.user_id or self.is_anonymized:
            return self

        full_name = getattr(self.user, 'get_full_name', lambda: '')().strip()
        self.customer_name = self.customer_name or full_name or self.user.email or ''
        self.customer_email = self.customer_email or getattr(self.user, 'email', None)
        self.customer_phone = self.customer_phone or getattr(self.user, 'phone', None)
        return self

    @classmethod
    def capacity_reserved_statuses(cls, *, include_drafts=True):
        """Return statuses that should reserve pickup slot capacity."""
        statuses = [
            cls.LEGACY_SUBMITTED_STATUS,
            cls.Status.PENDING,
            cls.Status.CONFIRMED,
            cls.Status.PREPARING,
            cls.Status.READY,
            cls.Status.COMPLETED,
        ]
        if include_drafts:
            statuses.append(cls.Status.DRAFT)
        return tuple(statuses)

    def can_transition_to(self, new_status: str) -> bool:
        """Return whether the order can move to the provided new status."""
        if not isinstance(new_status, str):
            return False

        normalized = new_status.lower()
        if normalized == self.status:
            return False

        try:
            normalized = self.Status(normalized)
        except ValueError:
            return False

        return normalized in self.STATUS_TRANSITIONS.get(self.status, set())

    def transition_to(self, new_status: str):
        """Validate and apply an in-memory status transition for the order."""
        normalized = new_status.lower() if isinstance(new_status, str) else new_status
        if not self.can_transition_to(normalized):
            raise OrderTransitionError(
                _("Cannot transition order from %(from_status)s to %(to_status)s."),
                params={'from_status': self.status, 'to_status': normalized},
            )

        self.status = normalized
        return self

    def is_active(self):
        """Return True while the order is still actionable on the operator side."""
        return self.status in self.ACTIVE_STATUSES

    def is_completed(self):
        """Return True when the operational lifecycle is finished."""
        return self.status == self.Status.COMPLETED

    def is_urgent(self, threshold_minutes=15):
        """Return True when the pickup time is close enough to deserve emphasis."""
        if not self.pickup_slot_id or self.status not in self.ACTIVE_STATUSES:
            return False
        delta = self.pickup_slot.start_time - timezone.now()
        return timedelta(minutes=0) <= delta <= timedelta(minutes=threshold_minutes)

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
        if self.status != self.Status.DRAFT:
            raise ValidationError("Cannot modify order after submission")

        if not item.is_available_now():
            raise ValidationError(f"Item '{item.name}' is not available")

        if quantity <= 0:
            raise ValidationError("Quantity must be positive")

        selected_options = selected_options or []
        item.validate_options(selected_options)

        # Calculate price and persist the order item
        unit_price = item.get_price_with_options(selected_options)

        order_item = OrderItem(
            order=self,
            item=item,
            quantity=quantity,
            unit_price=unit_price,
            options=[{'option_id': int(option_id)} for option_id in selected_options]
        )
        order_item.snapshot_pricing()
        order_item.save()

        if selected_options:
            option_qs = Option.objects.filter(
                id__in=selected_options,
                group__item=item,
                is_available=True
            )
            option_map = {option.id: option for option in option_qs}
            for option_id in selected_options:
                option = option_map.get(int(option_id))
                if option is None:
                    continue
                OrderItemOption.objects.create(
                    order_item=order_item,
                    option=option,
                    price_modifier=option.price_modifier
                )

        self._refresh_draft_financials()
        self.save(update_fields=['total_price', 'total_amount', 'tax_amount'])

    def add_combo(self, combo, quantity, combo_selections=None):
        """Add a combo to the order as a priced snapshot line."""
        if self.status != self.Status.DRAFT:
            raise ValidationError("Cannot modify order after submission")

        if combo.category.menu.food_truck_id != self.food_truck_id:
            raise ValidationError('Combo belongs to another food truck')

        if not combo.is_available:
            raise ValidationError(f"Combo '{combo.name}' is not available")

        if quantity <= 0:
            raise ValidationError("Quantity must be positive")

        snapshot = combo.build_order_snapshot(combo_selections=combo_selections)
        unit_price = snapshot['unit_price']

        order_item = OrderItem(
            order=self,
            combo=combo,
            quantity=quantity,
            unit_price=unit_price,
            options=snapshot['components'],
        )
        order_item.snapshot_pricing()
        order_item.save()

        for component in snapshot['components']:
            for option in component.get('selected_options', []):
                option_obj = Option.objects.filter(pk=option['option_id']).first()
                if option_obj is None:
                    continue
                OrderItemOption.objects.create(
                    order_item=order_item,
                    option=option_obj,
                    price_modifier=option_obj.price_modifier,
                )

        self._refresh_draft_financials()
        self.save(update_fields=['total_price', 'total_amount', 'tax_amount'])

    def calculate_total(self):
        """
        Calculate the total price from all order items.

        Returns:
            Decimal: Total price
        """
        return self.items.aggregate(
            total=models.Sum('total_price')
        )['total'] or Decimal('0.00')

    def calculate_tax_total(self):
        """Calculate the current tax total from item snapshots."""
        return self.items.aggregate(
            total=models.Sum('tax_amount')
        )['total'] or Decimal('0.00')

    def _refresh_draft_financials(self):
        """Keep draft order financial fields synchronized with line snapshots."""
        total = self.calculate_total()
        taxes = self.calculate_tax_total()
        self.total_price = total
        self.total_amount = total
        self.tax_amount = taxes

    def clear(self):
        """Remove all draft items from the order and reset totals."""
        if self.status != self.Status.DRAFT:
            raise ValidationError('Can only clear draft orders.')

        self.items.all().delete()
        self.total_price = Decimal('0.00')
        self.total_amount = Decimal('0.00')
        self.tax_amount = Decimal('0.00')
        self.save(update_fields=['total_price', 'total_amount', 'tax_amount'])

    def freeze_financials(self):
        """Compute and lock financial snapshot values before payment finalization."""
        if self.is_paid():
            raise ValidationError('Cannot freeze financials after payment.')

        self.total_amount = self.calculate_total()
        self.tax_amount = self.calculate_tax_total()
        self.total_price = self.total_amount
        self.save(update_fields=['total_price', 'total_amount', 'tax_amount', 'currency'])
        return self

    def can_be_submitted(self):
        """Return True when the draft order meets all submission requirements."""

        if self.status != self.Status.DRAFT:
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

        if self.status != self.Status.DRAFT:
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

            if self.status != self.Status.DRAFT:
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

            self.status = self.Status.PENDING
            self.submitted_at = timezone.now()
            self.save(update_fields=['status', 'submitted_at'])
        except OperationalError:
            raise ValidationError('Pickup slot is no longer available.')

    def is_paid(self) -> bool:
        """Return True when the order has a payment timestamp."""
        return self.paid_at is not None

    def assert_mutable(self):
        """Raise when trying to mutate a paid order."""
        if self.is_paid():
            AuditService.log(
                'order_modification_blocked',
                self,
                payload={'operation': 'assert_mutable'},
                user=self.user,
            )
            raise ValidationError('Paid orders are immutable.')

    @transaction.atomic
    def anonymize(self):
        """Remove personal data while preserving immutable financial records."""
        if self.is_anonymized:
            return self

        anonymized_at = timezone.now()
        Order.objects.filter(pk=self.pk).update(
            customer_name='ANONYMIZED',
            customer_email=None,
            customer_phone=None,
            is_anonymized=True,
            anonymized_at=anonymized_at,
        )
        self.refresh_from_db(fields=['customer_name', 'customer_email', 'customer_phone', 'is_anonymized', 'anonymized_at'])
        AuditService.log(
            'order_anonymized',
            self,
            payload={'anonymized_at': anonymized_at.isoformat(), 'paid_at': self.paid_at.isoformat() if self.paid_at else None},
            user=self.user,
        )
        return self

    def mark_as_paid(self):
        """Mark order as paid once, keeping the operation idempotent."""
        if self.is_paid():
            return self

        self.freeze_financials()

        self.paid_at = timezone.now()
        if self.status == self.Status.PENDING:
            self.status = self.Status.CONFIRMED
            self.save(update_fields=['paid_at', 'status'])
            AuditService.log('order_paid', self, payload={'status': self.status}, user=self.user)
            return self

        self.save(update_fields=['paid_at'])
        AuditService.log('order_paid', self, payload={'status': self.status}, user=self.user)
        return self

    def _has_paid_immutable_changes(self) -> bool:
        """Detect forbidden field changes once the order has been paid."""
        if not self.pk:
            return False

        original = Order.objects.filter(pk=self.pk).values(
            'user_id',
            'food_truck_id',
            'pickup_slot_id',
            'customer_name',
            'customer_email',
            'customer_phone',
            'is_anonymized',
            'total_price',
            'total_amount',
            'tax_amount',
            'currency',
            'submitted_at',
            'paid_at',
            'anonymized_at',
        ).first()
        if not original:
            return False

        return any([
            original['user_id'] != self.user_id,
            original['food_truck_id'] != self.food_truck_id,
            original['pickup_slot_id'] != self.pickup_slot_id,
            original['customer_name'] != self.customer_name,
            original['customer_email'] != self.customer_email,
            original['customer_phone'] != self.customer_phone,
            original['is_anonymized'] != self.is_anonymized,
            original['total_price'] != self.total_price,
            original['total_amount'] != self.total_amount,
            original['tax_amount'] != self.tax_amount,
            original['currency'] != self.currency,
            original['submitted_at'] != self.submitted_at,
            original['paid_at'] != self.paid_at,
            original['anonymized_at'] != self.anonymized_at,
        ])

    def save(self, *args, **kwargs):
        """Enforce immutability for paid orders at the model layer."""
        if not self.pk:
            self.snapshot_customer_data()

        was_paid = False
        if self.pk:
            was_paid = Order.objects.filter(pk=self.pk, paid_at__isnull=False).exists()

        if self.pk and was_paid:
            update_fields = kwargs.get('update_fields')
            if update_fields is not None:
                allowed_updates = {'status'}
                if not set(update_fields).issubset(allowed_updates):
                    AuditService.log(
                        'order_modification_blocked',
                        self,
                        payload={'update_fields': sorted(list(update_fields))},
                        user=self.user,
                    )
                    raise ValidationError('Paid orders are immutable.')
            elif self._has_paid_immutable_changes():
                AuditService.log(
                    'order_modification_blocked',
                    self,
                    payload={'update_fields': None},
                    user=self.user,
                )
                raise ValidationError('Paid orders are immutable.')

        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        """Prevent deletion of paid orders."""
        self.assert_mutable()
        return super().delete(*args, **kwargs)

    def clean(self):
        """Validate order constraints."""
        if self.status not in (self.Status.DRAFT, self.Status.CANCELLED):
            # For submitted operator-side orders, ensure all required data is present
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
    tax_rate = models.DecimalField(
        max_digits=6,
        decimal_places=4,
        help_text=_("Tax rate snapshot stored as a fraction")
    )
    tax_amount = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text=_("Tax amount snapshot for this line")
    )
    total_price = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        help_text=_("Total price for this item including tax")
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
            models.CheckConstraint(
                check=models.Q(tax_rate__gte=0),
                name='order_item_tax_rate_non_negative'
            ),
            models.CheckConstraint(
                check=models.Q(tax_amount__gte=0),
                name='order_item_tax_amount_non_negative'
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

    def _apply_snapshot_totals(self):
        """Compute totals from the already stored tax snapshot."""
        subtotal = (self.unit_price or Decimal('0.00')) * (self.quantity or 0)
        self.tax_amount = (subtotal * (self.tax_rate or Decimal('0.0000'))).quantize(Decimal('0.01'))
        self.total_price = (subtotal + self.tax_amount).quantize(Decimal('0.01'))

    def _resolve_tax_rate(self):
        from common.models import Tax

        if self.item_id:
            return self.item.get_tax_rate()

        default_tax = Tax.objects.default()
        if default_tax is None:
            raise ValidationError('No default tax configured.')
        return default_tax.rate

    def snapshot_pricing(self):
        """Store all financial data at order time without future tax recomputation."""
        if self.unit_price is None:
            raise ValidationError({'unit_price': 'unit_price is required.'})
        if not self.quantity:
            raise ValidationError({'quantity': 'quantity is required.'})

        self.tax_rate = self._resolve_tax_rate()
        self._apply_snapshot_totals()
        return self

    def clean(self):
        if self.tax_rate is None:
            raise ValidationError({'tax_rate': 'tax_rate is required.'})

    def save(self, *args, **kwargs):
        """Prevent writes after payment and store financial snapshots."""
        if self.order_id and self.order.is_paid():
            AuditService.log(
                'order_item_modification_blocked',
                self,
                payload={'order_id': self.order_id},
                user=self.order.user,
            )
            raise ValidationError('Order items are immutable after payment.')

        if self.tax_rate is None:
            self.snapshot_pricing()
        else:
            self._apply_snapshot_totals()
        self.clean()
        update_fields = kwargs.get('update_fields')
        if update_fields is not None:
            normalized_fields = set(update_fields)
            normalized_fields.update({'tax_rate', 'tax_amount', 'total_price'})
            kwargs['update_fields'] = sorted(normalized_fields)

        super().save(*args, **kwargs)

        if self.order_id and self.order.status == Order.Status.DRAFT:
            self.order._refresh_draft_financials()
            self.order.save(update_fields=['total_price', 'total_amount', 'tax_amount'])


class Ticket(models.Model):
    """Immutable fiscal ticket snapshot generated once per paid order."""

    order = models.OneToOneField(
        Order,
        on_delete=models.PROTECT,
        related_name='ticket',
    )
    number = models.CharField(max_length=32, unique=True)
    issued_at = models.DateTimeField(default=timezone.now)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    tax_amount = models.DecimalField(max_digits=10, decimal_places=2)
    payload = models.JSONField(default=dict)

    class Meta:
        verbose_name = _('Ticket')
        verbose_name_plural = _('Tickets')
        ordering = ['-issued_at']
        indexes = [
            models.Index(fields=['number']),
            models.Index(fields=['issued_at']),
        ]
        constraints = [
            models.CheckConstraint(check=models.Q(total_amount__gte=0), name='ticket_total_amount_non_negative'),
            models.CheckConstraint(check=models.Q(tax_amount__gte=0), name='ticket_tax_amount_non_negative'),
        ]

    def __str__(self):
        return self.number

    def save(self, *args, **kwargs):
        if self.pk and Ticket.objects.filter(pk=self.pk).exists():
            raise ValidationError('Ticket is immutable after creation.')
        return super().save(*args, **kwargs)


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
