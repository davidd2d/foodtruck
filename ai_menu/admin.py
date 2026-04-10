from django.contrib import admin
from .models import AIRecommendation


@admin.register(AIRecommendation)
class AIRecommendationAdmin(admin.ModelAdmin):
    """Admin interface for AIRecommendation model."""

    list_display = ('item', 'recommendation_type', 'status', 'created_at')
    list_filter = ('status', 'recommendation_type', 'created_at')
    search_fields = ('item__name', 'item__category__menu__food_truck__name')
    readonly_fields = ('created_at', 'updated_at', 'payload')
    fieldsets = (
        (None, {
            'fields': ('item', 'recommendation_type', 'status')
        }),
        ('Recommendation Data', {
            'fields': ('payload',),
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )

    def get_queryset(self, request):
        """Optimize queryset with select_related."""
        queryset = super().get_queryset(request)
        return queryset.select_related('item__category__menu__food_truck')

    actions = ['accept_recommendations', 'reject_recommendations']

    def accept_recommendations(self, request, queryset):
        """Admin action to accept pending recommendations."""
        pending = queryset.filter(status='pending')
        updated_count = 0
        for rec in pending:
            rec.accept()
            updated_count += 1
        self.message_user(request, f"{updated_count} recommendations accepted.")

    accept_recommendations.short_description = "Accept selected pending recommendations"

    def reject_recommendations(self, request, queryset):
        """Admin action to reject pending recommendations."""
        pending = queryset.filter(status='pending')
        updated_count = 0
        for rec in pending:
            rec.reject()
            updated_count += 1
        self.message_user(request, f"{updated_count} recommendations rejected.")

    reject_recommendations.short_description = "Reject selected pending recommendations"
