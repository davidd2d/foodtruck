from django.db import models
from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _

User = get_user_model()


class OnboardingImport(models.Model):
    """Model for storing user-provided data for AI-powered onboarding."""

    STATUS_CHOICES = [
        ('pending', _('Pending')),
        ('processing', _('Processing')),
        ('completed', _('Completed')),
        ('failed', _('Failed')),
    ]

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='onboarding_imports',
        help_text=_('User who initiated the import')
    )
    raw_text = models.TextField(
        blank=True,
        help_text=_('Raw text input from user (e.g., copied from Instagram, website)')
    )
    images = models.JSONField(
        default=list,
        blank=True,
        help_text=_('List of uploaded image file paths or URLs')
    )
    source_url = models.URLField(
        blank=True,
        null=True,
        help_text=_('Optional reference URL (not scraped automatically)')
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending',
        help_text=_('Current processing status')
    )
    parsed_data = models.JSONField(
        default=dict,
        blank=True,
        help_text=_('Structured data extracted by AI processing')
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text=_('Timestamp when import was created')
    )

    class Meta:
        verbose_name = _('Onboarding Import')
        verbose_name_plural = _('Onboarding Imports')
        ordering = ['-created_at']

    def __str__(self):
        return f"Onboarding Import for {self.user.email} - {self.status}"
