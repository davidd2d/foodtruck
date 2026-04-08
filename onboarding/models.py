from django.db import models
from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _

User = get_user_model()


def onboarding_upload_path(instance, filename):
    """Generate upload path for onboarding images."""
    return f"onboarding/user_{instance.import_instance.user_id}/import_{instance.import_instance.id}/raw/{filename}"


class OnboardingImage(models.Model):
    """Model for storing uploaded images for onboarding imports."""

    import_instance = models.ForeignKey(
        "OnboardingImport",
        related_name="image_files",
        on_delete=models.CASCADE
    )
    image = models.ImageField(upload_to=onboarding_upload_path)
    image_type = models.CharField(
        max_length=20,
        choices=[
            ("menu", "Menu"),
            ("logo", "Logo"),
            ("other", "Other"),
        ],
        default="menu"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _('Onboarding Image')
        verbose_name_plural = _('Onboarding Images')
        ordering = ['-created_at']

    def __str__(self):
        return f"Image for {self.import_instance} - {self.image.name}"


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
    images = models.ManyToManyField(
        "OnboardingImage",
        blank=True,
        related_name="imports",
        help_text=_('Uploaded images for AI processing')
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

    def cleanup_files(self):
        """Delete all associated uploaded files."""
        for image_file in self.image_files.all():
            try:
                image_file.image.delete(save=False)
            except Exception:
                # Log but don't fail if file deletion fails
                pass
        # Clear the many-to-many relationship
        self.images.clear()
