from django.db import models
from django.utils.translation import gettext_lazy as _


class OpenAgendaSource(models.Model):
    """Configuration of OpenAgenda agendas used for event synchronization."""

    name = models.CharField(max_length=120, blank=True, default='')
    agenda_uid = models.CharField(max_length=64, unique=True, db_index=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _('OpenAgenda Source')
        verbose_name_plural = _('OpenAgenda Sources')
        ordering = ['name', 'agenda_uid']

    def __str__(self):
        return self.name or self.agenda_uid


class Event(models.Model):
    """Represents an external event that may impact food truck demand."""

    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, default='')
    latitude = models.DecimalField(max_digits=9, decimal_places=6, db_index=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, db_index=True)
    start_date = models.DateField()
    end_date = models.DateField()
    expected_attendance = models.PositiveIntegerField(null=True, blank=True)
    location_text = models.CharField(max_length=255, blank=True, default='')
    image_url = models.URLField(max_length=500, blank=True, default='')
    source_url = models.URLField(max_length=500, blank=True, default='')
    category = models.CharField(max_length=64, blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _('Event')
        verbose_name_plural = _('Events')
        ordering = ['start_date', 'name']
        indexes = [
            models.Index(fields=['start_date', 'end_date']),
        ]

    def __str__(self):
        return self.name


class EventOpportunity(models.Model):
    """Stores event opportunity evaluations for one food truck."""

    foodtruck = models.ForeignKey(
        'foodtrucks.FoodTruck',
        on_delete=models.CASCADE,
        related_name='event_opportunities',
    )
    event = models.ForeignKey(
        Event,
        on_delete=models.CASCADE,
        related_name='opportunities',
    )
    opportunity_score = models.FloatField(help_text=_('Score from 0 to 100'))
    predicted_revenue = models.DecimalField(max_digits=10, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _('Event Opportunity')
        verbose_name_plural = _('Event Opportunities')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['foodtruck', 'event']),
            models.Index(fields=['-created_at']),
        ]

    def __str__(self):
        return f"{self.foodtruck.name} / {self.event.name}: {self.opportunity_score:.1f}"


class EventAIAnalysis(models.Model):
    """Persistent record of an AI-powered analysis of a single event."""

    class Provider(models.TextChoices):
        OPENAI = 'openai', _('OpenAI')

    event = models.OneToOneField(
        Event,
        on_delete=models.CASCADE,
        related_name='ai_analysis',
    )
    provider = models.CharField(max_length=32, choices=Provider.choices, default=Provider.OPENAI)
    model_name = models.CharField(max_length=64)
    prompt_version = models.CharField(max_length=16, db_index=True)
    raw_response = models.JSONField()
    normalized_data = models.JSONField()
    confidence_score = models.FloatField(help_text=_('Confidence returned by the AI, 0.0–1.0'))
    analyzed_at = models.DateTimeField(db_index=True)
    processing_time_ms = models.PositiveIntegerField()
    token_usage_input = models.PositiveIntegerField()
    token_usage_output = models.PositiveIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _('Event AI Analysis')
        verbose_name_plural = _('Event AI Analyses')
        ordering = ['-analyzed_at']
        indexes = [
            models.Index(fields=['provider', 'model_name']),
            models.Index(fields=['prompt_version']),
            models.Index(fields=['-analyzed_at']),
        ]

    def __str__(self) -> str:
        return f"AI analysis of '{self.event.name}' [{self.prompt_version}]"


class RevenuePrediction(models.Model):
    """Stores explainable daily revenue predictions for one food truck."""

    foodtruck = models.ForeignKey(
        'foodtrucks.FoodTruck',
        on_delete=models.CASCADE,
        related_name='revenue_predictions',
    )
    date = models.DateField(db_index=True)
    predicted_revenue = models.DecimalField(max_digits=10, decimal_places=2)
    confidence_score = models.FloatField(help_text=_('Confidence score from 0 to 1'))
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _('Revenue Prediction')
        verbose_name_plural = _('Revenue Predictions')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['foodtruck', 'date']),
            models.Index(fields=['-created_at']),
        ]

    def __str__(self):
        return f"{self.foodtruck.name} / {self.date}: {self.predicted_revenue}"
