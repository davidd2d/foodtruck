from django.db import models
from django.utils.translation import gettext_lazy as _
from django.core.exceptions import ValidationError


class AIRecommendationQuerySet(models.QuerySet):
    """Custom QuerySet for AIRecommendation model."""

    def pending(self):
        """Return only pending recommendations."""
        return self.filter(status='pending')

    def accepted(self):
        """Return only accepted recommendations."""
        return self.filter(status='accepted')

    def rejected(self):
        """Return only rejected recommendations."""
        return self.filter(status='rejected')

    def for_foodtruck(self, foodtruck):
        """Filter by food truck."""
        return self.filter(item__category__menu__food_truck=foodtruck)

    def for_item(self, item):
        """Filter by item."""
        return self.filter(item=item)


class AIRecommendationManager(models.Manager):
    """Custom manager for AIRecommendation model."""

    def get_queryset(self):
        """Return the custom QuerySet."""
        return AIRecommendationQuerySet(self.model, using=self._db)

    def pending(self):
        """Return pending recommendations."""
        return self.get_queryset().pending()

    def accepted(self):
        """Return accepted recommendations."""
        return self.get_queryset().accepted()

    def rejected(self):
        """Return rejected recommendations."""
        return self.get_queryset().rejected()

    def for_foodtruck(self, foodtruck):
        """Filter by food truck."""
        return self.get_queryset().for_foodtruck(foodtruck)

    def for_item(self, item):
        """Filter by item."""
        return self.get_queryset().for_item(item)


class AIRecommendation(models.Model):
    """
    Stores AI-generated recommendations for menu items.

    Recommendations can be suggestions for free options, paid options,
    bundles, or pricing adjustments. Each recommendation has a status
    (pending, accepted, rejected) allowing owners to curate AI suggestions.
    """

    RECOMMENDATION_CHOICES = [
        ('free_option', _('Free Option')),
        ('paid_option', _('Paid Option')),
        ('bundle', _('Bundle')),
        ('pricing', _('Pricing')),
    ]

    STATUS_CHOICES = [
        ('pending', _('Pending')),
        ('accepted', _('Accepted')),
        ('rejected', _('Rejected')),
    ]

    # Relations
    item = models.ForeignKey(
        'menu.Item',
        on_delete=models.CASCADE,
        related_name='ai_recommendations',
        help_text=_("The menu item this recommendation is for")
    )

    # Classification
    recommendation_type = models.CharField(
        max_length=20,
        choices=RECOMMENDATION_CHOICES,
        help_text=_("Type of recommendation")
    )

    # Data
    payload = models.JSONField(
        default=dict,
        blank=True,
        help_text=_("Structured recommendation data (varies by type)")
    )

    # Status
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending',
        help_text=_("Current status of the recommendation")
    )

    # Metadata
    created_at = models.DateTimeField(auto_now_add=True, help_text=_("When the recommendation was created"))
    updated_at = models.DateTimeField(auto_now=True, help_text=_("When the recommendation was last updated"))

    objects = AIRecommendationManager()

    class Meta:
        verbose_name = _("AI Recommendation")
        verbose_name_plural = _("AI Recommendations")
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['item', 'status']),
            models.Index(fields=['recommendation_type', 'status']),
            models.Index(fields=['status', '-created_at']),
            models.Index(fields=['-created_at']),
        ]

    def __str__(self):
        return f"{self.item.name} - {self.get_recommendation_type_display()} ({self.get_status_display()})"

    def is_pending(self):
        """Check if recommendation is pending."""
        return self.status == 'pending'

    def accept(self):
        """Accept this recommendation."""
        if self.status != 'pending':
            raise ValidationError(_("Only pending recommendations can be accepted."))
        self.status = 'accepted'
        self.save(update_fields=['status', 'updated_at'])

    def reject(self):
        """Reject this recommendation."""
        if self.status != 'pending':
            raise ValidationError(_("Only pending recommendations can be rejected."))
        self.status = 'rejected'
        self.save(update_fields=['status', 'updated_at'])

    def reset_to_pending(self):
        """Move an accepted or rejected recommendation back to pending."""
        if self.status == 'pending':
            raise ValidationError(_("This recommendation is already pending."))
        self.status = 'pending'
        self.save(update_fields=['status', 'updated_at'])
