from django.contrib import admin
from .models import Preference


@admin.register(Preference)
class PreferenceAdmin(admin.ModelAdmin):
    """Preference admin - read-only for non-superusers."""
    list_display = ('name', 'slug', 'description')
    search_fields = ('name', 'slug')
    prepopulated_fields = {'slug': ('name',)}

    def has_change_permission(self, request, obj=None):
        """Only superusers can change preferences."""
        return request.user.is_superuser

    def has_delete_permission(self, request, obj=None):
        """Only superusers can delete preferences."""
        return request.user.is_superuser

    def has_add_permission(self, request):
        """Only superusers can add preferences."""
        return request.user.is_superuser
