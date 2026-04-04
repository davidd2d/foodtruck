from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User


@admin.register(User)
class UserAdmin(UserAdmin):
    """User admin - only superusers can manage users."""
    model = User
    ordering = ('email',)
    search_fields = ('email', 'first_name', 'last_name')
    list_filter = ('is_staff', 'is_superuser', 'is_active')

    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        ('Personal info', {'fields': ('first_name', 'last_name')}),
        ('Permissions', {'fields': ('is_staff', 'is_superuser', 'is_active', 'groups', 'user_permissions')}),
        ('Important dates', {'fields': ('last_login', 'date_joined')}),
    )

    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'password1', 'password2'),
        }),
    )

    filter_horizontal = ('groups', 'user_permissions')
    list_display = ('email', 'is_staff', 'is_superuser')

    def has_view_permission(self, request, obj=None):
        """Only superusers can view users."""
        return request.user.is_superuser

    def has_change_permission(self, request, obj=None):
        """Only superusers can change users."""
        return request.user.is_superuser

    def has_delete_permission(self, request, obj=None):
        """Only superusers can delete users."""
        return request.user.is_superuser

    def has_add_permission(self, request):
        """Only superusers can add users."""
        return request.user.is_superuser

