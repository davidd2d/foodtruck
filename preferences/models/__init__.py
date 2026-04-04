from django.db import models
from django.utils.text import slugify
from django.utils.translation import gettext_lazy as _


class Preference(models.Model):
    """
    Represents a dietary preference or restriction.

    This model is designed to be flexible and extensible, supporting
    any type of dietary preference such as vegan, halal, gluten-free, etc.
    """
    name = models.CharField(max_length=100, unique=True, help_text=_("Name of the dietary preference"))
    slug = models.SlugField(max_length=100, unique=True, help_text=_("URL-friendly identifier"))
    description = models.TextField(blank=True, help_text=_("Optional description of the preference"))

    class Meta:
        verbose_name = _("Preference")
        verbose_name_plural = _("Preferences")
        ordering = ['name']

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)
