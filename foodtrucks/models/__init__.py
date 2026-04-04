import math
from django.conf import settings
from django.db import models
from django.db.models import Q
from django.utils import timezone
from django.utils.text import slugify
from django.utils.translation import gettext_lazy as _
from django.urls import reverse
from decimal import Decimal


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
        return FoodTruckQuerySet(self.model, using=self._db).select_related(
            'subscription__plan'
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
        Automatically generate a unique slug on create.
        """
        if not self.slug:
            self.slug = self._build_unique_slug()
        super().save(*args, **kwargs)

    def is_open(self):
        """
        Check if the food truck is currently open.

        Placeholder implementation - returns True.
        In production, this would check operating hours, holidays, etc.
        """
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

        if not hasattr(self, 'subscription') or not self.subscription.is_active():
            return False

        return self.subscription.plan.allows_ordering

    def get_plan(self):
        """
        Get the current plan for this food truck.

        Returns:
            Plan: The current plan, or None if no subscription
        """
        if hasattr(self, 'subscription'):
            return self.subscription.plan
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
