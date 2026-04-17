from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.utils import timezone


class TaxQuerySet(models.QuerySet):
    def active(self):
        return self.filter(is_active=True)

    def for_country(self, country=None):
        queryset = self.active()
        if not country:
            return queryset
        return queryset.filter(models.Q(country__iexact=country) | models.Q(country__isnull=True) | models.Q(country=''))

    def default(self, country=None):
        queryset = self.for_country(country)
        exact_match = None
        if country:
            exact_match = queryset.filter(country__iexact=country, is_default=True).first()
            if exact_match:
                return exact_match
        return queryset.filter(is_default=True).order_by('country', 'name').first()


class Tax(models.Model):
    name = models.CharField(max_length=120)
    rate = models.DecimalField(max_digits=5, decimal_places=4)
    country = models.CharField(max_length=2, null=True, blank=True)
    is_active = models.BooleanField(default=True)
    is_default = models.BooleanField(default=False)
    created_at = models.DateTimeField(default=timezone.now, db_index=True)

    objects = TaxQuerySet.as_manager()

    class Meta:
        ordering = ['country', '-is_default', 'name']
        constraints = [
            models.CheckConstraint(
                check=models.Q(rate__gte=Decimal('0.0000')) & models.Q(rate__lte=Decimal('1.0000')),
                name='common_tax_rate_between_zero_and_one',
            ),
            models.UniqueConstraint(
                fields=['is_default'],
                condition=models.Q(is_default=True),
                name='common_single_default_tax',
            ),
        ]

    def __str__(self):
        if self.country:
            return f"{self.name} [{self.country}] ({self.rate})"
        return f"{self.name} ({self.rate})"

    def clean(self):
        if self.rate is None:
            raise ValidationError({'rate': 'Tax rate is required.'})
        if self.rate < Decimal('0.0000') or self.rate > Decimal('1.0000'):
            raise ValidationError({'rate': 'Tax rate must be between 0 and 1.'})
        if self.country:
            self.country = self.country.upper()
            if len(self.country) != 2:
                raise ValidationError({'country': 'Country must be an ISO 3166-1 alpha-2 code.'})

    def save(self, *args, **kwargs):
        self.clean()
        with transaction.atomic():
            if self.is_default:
                Tax.objects.exclude(pk=self.pk).filter(is_default=True).update(is_default=False)
            return super().save(*args, **kwargs)


class AuditLog(models.Model):
    """Immutable audit trail for critical business and compliance events."""

    action = models.CharField(max_length=128, db_index=True)
    model = models.CharField(max_length=128, db_index=True)
    object_id = models.CharField(max_length=64, db_index=True)
    payload = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(default=timezone.now, db_index=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='audit_logs',
    )

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['created_at']),
            models.Index(fields=['action', 'created_at']),
            models.Index(fields=['model', 'object_id']),
        ]

    def __str__(self):
        return f"{self.action} {self.model}#{self.object_id}"

    @classmethod
    def log_event(cls, *, action, model, object_id, payload=None, user=None):
        return cls.objects.create(
            action=action,
            model=model,
            object_id=str(object_id),
            payload=payload or {},
            user=user,
        )
