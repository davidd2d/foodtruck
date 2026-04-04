from django.contrib import admin
from django.utils.translation import gettext_lazy as _
from .models import OnboardingImport


@admin.register(OnboardingImport)
class OnboardingImportAdmin(admin.ModelAdmin):
    list_display = ['id', 'user', 'status', 'created_at']
    list_filter = ['status', 'created_at']
    search_fields = ['user__email', 'raw_text']
    readonly_fields = ['parsed_data', 'created_at']
    fieldsets = (
        (_('Basic Information'), {
            'fields': ('user', 'status', 'created_at')
        }),
        (_('Input Data'), {
            'fields': ('raw_text', 'images', 'source_url')
        }),
        (_('Processed Data'), {
            'fields': ('parsed_data',),
            'classes': ('collapse',)
        }),
    )
