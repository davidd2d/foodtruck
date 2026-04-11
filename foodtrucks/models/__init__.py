import math
import pytz
from datetime import timedelta

from django.conf import settings
from django.db import models
from django.db.models import Q, Count, F
from django.utils import timezone
from django.utils.text import slugify
from django.utils.translation import gettext_lazy as _
from django.urls import reverse
from decimal import Decimal

PARIS_TZ = pytz.timezone('Europe/Paris')


class Plan(models.Model):
    """
    Represents a subscription plan for food trucks.

    Defines the features and pricing for different plan tiers.
    Designed to be extensible for future plans.
    """
    name = models.CharField(max_length=100, help_text=_("Display name of the plan"))
    code = models.CharField(
        max_length=50,
        unique=True,
        help_text=_("Unique code identifier for the plan")
    )
    price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text=_("Monthly price of the plan")
    )
    allows_ordering = models.BooleanField(
        default=False,
        help_text=_("Whether this plan allows accepting orders")
    )
    created_at = models.DateTimeField(auto_now_add=True, help_text=_("When the plan was created"))

    class Meta:
        verbose_name = _("Plan")
        verbose_name_plural = _("Plans")
        ordering = ['price']

    def __str__(self):
        return f"{self.name} ({self.code})"


class Subscription(models.Model):
    """
    Represents a food truck's subscription to a plan.

    Manages subscription lifecycle and billing periods.
    """

    STATUS_CHOICES = [
        ('active', 'Active'),
        ('inactive', 'Inactive'),
        ('cancelled', 'Cancelled'),
    ]

    food_truck = models.OneToOneField(
        'FoodTruck',
        on_delete=models.CASCADE,
        related_name='subscription',
        help_text=_("The food truck this subscription belongs to")
    )
    plan = models.ForeignKey(
        Plan,
        on_delete=models.PROTECT,
        related_name='subscriptions',
        help_text=_("The plan this subscription is for")
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='active',
        help_text=_("Current status of the subscription")
    )
    start_date = models.DateTimeField(
        default=timezone.now,
        help_text=_("When the subscription started")
    )
    end_date = models.DateTimeField(
        blank=True,
        null=True,
        help_text=_("When the subscription ends (null for ongoing)")
    )
    created_at = models.DateTimeField(auto_now_add=True, help_text=_("When the subscription was created"))

    class Meta:
        verbose_name = _("Subscription")
        verbose_name_plural = _("Subscriptions")
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status']),
            models.Index(fields=['end_date']),
        ]

    def __str__(self):
        return f"{self.food_truck.name} - {self.plan.name}"

    def is_active(self):
        """
        Check if the subscription is currently active.

        Returns:
            bool: True if subscription is active and not expired
        """
        if self.status != 'active':
            return False

        if self.end_date and timezone.now() >= self.end_date:
            return False

        return True


class FoodTruckQuerySet(models.QuerySet):
    def active(self):
        """Return only active food trucks."""
        return self.filter(is_active=True)

    def nearby(self, lat, lng, radius_km):
        """
        Return food trucks within the specified radius using approximate bounding box.

        This uses a simple latitude/longitude range approximation for performance.
        For more precision, use the distance_to method on individual instances.
        """
        # Approximate: 1 degree latitude ~ 111 km
        # 1 degree longitude ~ 111 km * cos(lat)
        lat_delta = radius_km / 111.0
        lng_delta = radius_km / (111.0 * math.cos(math.radians(lat)))

        lat_min = lat - lat_delta
        lat_max = lat + lat_delta
        lng_min = lng - lng_delta
        lng_max = lng + lng_delta

        return self.filter(
            latitude__range=(lat_min, lat_max),
            longitude__range=(lng_min, lng_max)
        )


class FoodTruckManager(models.Manager):
    def get_queryset(self):
        return (
            FoodTruckQuerySet(self.model, using=self._db)
            .select_related('subscription__plan')
            .prefetch_related('menus__categories__items')
        )


class FoodTruck(models.Model):
    """
    Represents a food truck in the platform.

    Contains all business logic related to food truck operations,
    including availability, location calculations, and preference support.
    """
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='foodtrucks',
        help_text=_("The user who owns this food truck")
    )
    default_language = models.CharField(
        max_length=10,
        choices=settings.LANGUAGES,
        default=settings.LANGUAGE_CODE,
        help_text=_("Primary content language for this food truck and its menu")
    )
    name = models.CharField(max_length=200, help_text=_("Name of the food truck"))
    description = models.TextField(blank=True, help_text=_("Description of the food truck"))
    is_active = models.BooleanField(default=True, help_text=_("Whether the food truck is active"))
    created_at = models.DateTimeField(auto_now_add=True, help_text=_("When the food truck was created"))

    # Branding
    logo = models.ImageField(
        upload_to='foodtrucks/logos/',
        blank=True,
        null=True,
        help_text=_("Logo image for the food truck")
    )
    cover_image = models.ImageField(
        upload_to='foodtrucks/covers/',
        blank=True,
        null=True,
        help_text=_("Cover image for the food truck")
    )
    primary_color = models.CharField(
        max_length=7,
        default='#000000',
        help_text=_("Primary brand color (hex code)")
    )
    secondary_color = models.CharField(
        max_length=7,
        default='#FFFFFF',
        help_text=_("Secondary brand color (hex code)")
    )

    slug = models.SlugField(
        max_length=255,
        unique=True,
        blank=True,
        help_text=_("SEO-friendly resource slug")
    )

    # Location
    latitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        help_text=_("Latitude coordinate"),
        db_index=True
    )
    longitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        help_text=_("Longitude coordinate"),
        db_index=True
    )

    def get_base_coordinates(self):
        return (float(self.latitude), float(self.longitude))

    def get_current_location_for_schedule(self, schedule):
        return schedule.get_effective_location()

    # Preferences
    supported_preferences = models.ManyToManyField(
        'preferences.Preference',
        blank=True,
        help_text=_("Dietary preferences this food truck supports")
    )

    objects = FoodTruckManager()

    class Meta:
        verbose_name = _("Food Truck")
        verbose_name_plural = _("Food Trucks")
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['is_active']),
        ]

    def __str__(self):
        return self.name

    def get_content_language(self):
        """Return the primary content language for this food truck."""
        return self.default_language or settings.LANGUAGE_CODE

    def get_default_menu_name(self):
        """Return a default menu name in the food truck content language."""
        menu_labels = {
            'en': 'Menu',
            'fr': 'Carte',
            'es': 'Carta',
        }
        menu_label = menu_labels.get(self.get_content_language(), 'Menu')
        return f"{self.name} {menu_label}"

    def get_absolute_url(self):
        """
        Return the canonical URL for this food truck.
        """
        return reverse('foodtrucks:foodtruck-detail', kwargs={'slug': self.slug})

    def _build_unique_slug(self):
        base_slug = slugify(self.name) or 'foodtruck'
        slug = base_slug
        counter = 1
        while FoodTruck.objects.filter(slug=slug).exclude(pk=self.pk).exists():
            slug = f"{base_slug}-{counter}"
            counter += 1
        return slug

    def save(self, *args, **kwargs):
        """
        Automatically generate a unique slug on create and when the name changes.
        """
        should_regenerate_slug = not self.slug
        if self.pk and not should_regenerate_slug:
            previous_name = FoodTruck.objects.filter(pk=self.pk).values_list('name', flat=True).first()
            should_regenerate_slug = previous_name is not None and previous_name != self.name

        if should_regenerate_slug:
            self.slug = self._build_unique_slug()
        super().save(*args, **kwargs)

    def is_open(self):
        """
        Check if the food truck is currently open.

        Placeholder implementation - returns True.
        In production, this would check operating hours, holidays, etc.
        """
        return True

    def has_active_subscription(self) -> bool:
        """
        Return True when the foodtruck has an active subscription that allows ordering.
        """
        subscription = (
            Subscription.objects.select_related('plan')
            .filter(food_truck=self)
            .order_by('-start_date')
            .first()
        )

        if not subscription or not subscription.is_active():
            return False

        plan = subscription.plan
        if not plan or not getattr(plan, 'allows_ordering', False):
            return False

        return True

    def can_accept_orders(self):
        """
        Check if the food truck can accept orders.

        Returns True only if:
        - Food truck is active
        - Has an active subscription
        - Subscription plan allows ordering

        Returns:
            bool: True if orders can be accepted
        """
        if not self.is_active:
            return False

        return self.has_active_subscription() and self.is_open()

    def can_display_menu(self):
        """
        Determine if the food truck has a menu worth displaying.

        The menu display state is independent of subscription status and
        relies solely on whether an active menu exists with available items.
        """
        return self.menus.filter(
            is_active=True,
            categories__items__is_available=True,
        ).exists()

    def get_available_slots(self, target_date=None):
        """
        Return generated slots for the requested date.

        This method ensures slots are generated via the schedule service before returning
        only future, available slots.
        """
        from orders.services.schedule_service import generate_slots_for_date

        target_date = target_date or timezone.localdate()
        generate_slots_for_date(self, target_date)
        paris_now = timezone.localtime(timezone.now(), PARIS_TZ)

        slots = self.pickup_slots.filter(
            start_time__date=target_date,
            end_time__gt=paris_now,
        ).annotate(
            reserved=Count(
                'orders',
                filter=Q(orders__status__in=['draft', 'submitted', 'paid'])
            )
        ).filter(reserved__lt=F('capacity')).select_related(
            'service_schedule'
        ).order_by('start_time')
        return slots

    def get_current_service_schedule(self, reference_time=None):
        """Return the currently active schedule for the provided Paris time."""
        from orders.models import ServiceSchedule

        reference_time = timezone.localtime(reference_time or timezone.now(), PARIS_TZ)
        return (
            ServiceSchedule.objects.filter(
                food_truck=self,
                is_active=True,
                day_of_week=reference_time.weekday(),
                start_time__lte=reference_time.time(),
                end_time__gt=reference_time.time(),
            )
            .order_by('start_time')
            .first()
        )

    def get_next_available_service_schedule(self, after_schedule=None, reference_time=None):
        """Return the next chronological active schedule after the provided reference."""
        from orders.models import ServiceSchedule

        reference_time = timezone.localtime(reference_time or timezone.now(), PARIS_TZ)
        schedules = ServiceSchedule.objects.filter(
            food_truck=self,
            is_active=True,
        ).order_by('day_of_week', 'start_time')

        if not schedules.exists():
            return None

        for day_offset in range(0, 7):
            weekday = (reference_time.weekday() + day_offset) % 7
            day_schedules = schedules.filter(day_of_week=weekday)

            if day_offset == 0:
                if after_schedule is not None:
                    day_schedules = day_schedules.filter(start_time__gte=after_schedule.end_time)
                else:
                    day_schedules = day_schedules.filter(start_time__gt=reference_time.time())

            next_schedule = day_schedules.order_by('start_time').first()
            if next_schedule is not None:
                return next_schedule

        return None

    def _get_schedule_date(self, schedule, reference_time=None):
        """Return the next calendar date matching the provided schedule."""
        reference_time = timezone.localtime(reference_time or timezone.now(), PARIS_TZ)
        days_ahead = (schedule.day_of_week - reference_time.weekday() + 7) % 7
        target_date = reference_time.date() + timedelta(days=days_ahead)

        if days_ahead == 0 and schedule.end_time <= reference_time.time():
            target_date += timedelta(days=7)

        return target_date

    def get_recommended_pickup_slots(self, reference_time=None):
        """Return the best slot collection for ordering: current service first, next service otherwise."""
        reference_time = timezone.localtime(reference_time or timezone.now(), PARIS_TZ)

        if not self.can_accept_orders():
            return self.pickup_slots.none()

        current_schedule = self.get_current_service_schedule(reference_time=reference_time)
        if current_schedule is not None:
            current_slots = self.get_available_slots(reference_time.date()).filter(
                service_schedule=current_schedule,
            )
            if current_slots.exists():
                return current_slots

        today_slots = self.get_available_slots(reference_time.date())
        if today_slots.exists():
            return today_slots

        next_schedule = self.get_next_available_service_schedule(
            after_schedule=current_schedule,
            reference_time=reference_time,
        )
        if next_schedule is None:
            return self.pickup_slots.none()

        target_date = self._get_schedule_date(next_schedule, reference_time=reference_time)
        return self.get_available_slots(target_date).filter(service_schedule=next_schedule)

    def get_best_default_pickup_slot(self, reference_time=None):
        """Return the best default pickup slot using current then future service priority."""
        return self.get_recommended_pickup_slots(reference_time=reference_time).first()

    def get_plan(self):
        """
        Get the current plan for this food truck.

        Returns:
            Plan: The current plan, or None if no subscription
        """
        if hasattr(self, 'subscription'):
            return self.subscription.plan
        return None

    def get_primary_color(self):
        """Return a valid primary color for branding fallbacks."""
        return self.primary_color or '#000000'

    def get_secondary_color(self):
        """Return a valid secondary color for branding fallbacks."""
        return self.secondary_color or '#f8f9fa'

    def get_logo_url(self):
        """Return logo URL when available (None otherwise)."""
        if self.logo and hasattr(self.logo, 'url'):
            return self.logo.url
        return None

    def distance_to(self, lat, lng):
        """
        Calculate the distance to a given location using the Haversine formula.

        Args:
            lat: Target latitude
            lng: Target longitude

        Returns:
            Distance in kilometers (float)
        """
        # Haversine formula
        R = 6371  # Earth radius in kilometers

        lat1_rad = math.radians(float(self.latitude))
        lng1_rad = math.radians(float(self.longitude))
        lat2_rad = math.radians(float(lat))
        lng2_rad = math.radians(float(lng))

        dlat = lat2_rad - lat1_rad
        dlng = lng2_rad - lng1_rad

        a = (
            math.sin(dlat / 2) ** 2 +
            math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlng / 2) ** 2
        )
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

        return R * c

    def supports_preferences(self, preferences):
        """
        Check if the food truck supports all given preferences.

        Args:
            preferences: List of Preference instances or IDs

        Returns:
            True if all preferences are supported, False otherwise
        """
        if not preferences:
            return True

        supported_ids = set(self.supported_preferences.values_list('id', flat=True))
        required_ids = set(p.id if hasattr(p, 'id') else p for p in preferences)

        return required_ids.issubset(supported_ids)
