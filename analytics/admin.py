from django.contrib import admin

from analytics.models import Event, EventOpportunity, OpenAgendaSource, RevenuePrediction


@admin.register(OpenAgendaSource)
class OpenAgendaSourceAdmin(admin.ModelAdmin):
    list_display = ('name', 'agenda_uid', 'is_active', 'created_at')
    list_filter = ('is_active',)
    search_fields = ('name', 'agenda_uid')
    ordering = ('name', 'agenda_uid')


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ('name', 'start_date', 'end_date', 'expected_attendance', 'latitude', 'longitude', 'created_at')
    list_filter = ('start_date', 'end_date')
    search_fields = ('name',)
    ordering = ('start_date', 'name')


@admin.register(EventOpportunity)
class EventOpportunityAdmin(admin.ModelAdmin):
    list_display = ('foodtruck', 'event', 'opportunity_score', 'predicted_revenue', 'created_at')
    list_filter = ('created_at',)
    search_fields = ('foodtruck__name', 'event__name')
    autocomplete_fields = ('foodtruck', 'event')
    ordering = ('-created_at',)


@admin.register(RevenuePrediction)
class RevenuePredictionAdmin(admin.ModelAdmin):
    list_display = ('foodtruck', 'date', 'predicted_revenue', 'confidence_score', 'created_at')
    list_filter = ('date', 'created_at')
    search_fields = ('foodtruck__name',)
    autocomplete_fields = ('foodtruck',)
    ordering = ('-date',)
