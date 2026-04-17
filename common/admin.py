from django.contrib import admin
from common.models import AuditLog, Tax


class OwnerRestrictedAdminMixin:
    """
    Mixin to restrict admin access based on ownership.

    - Superusers have full access
    - Food truck owners can only see/edit their own objects
    - Others have no access

    Usage:
        class MyModelAdmin(OwnerRestrictedAdminMixin, admin.ModelAdmin):
            # Must implement:
            # - _filter_by_food_trucks(self, qs, truck_ids)
            # - _object_belongs_to_trucks(self, obj, truck_ids)
    """

    def get_queryset(self, request):
        """Filter queryset based on user permissions."""
        qs = super().get_queryset(request)

        if request.user.is_superuser:
            return qs

        # For food truck owners, filter by their food trucks
        if hasattr(request.user, 'foodtrucks'):
            # Get food truck IDs owned by this user
            owned_truck_ids = request.user.foodtrucks.values_list('id', flat=True)
            return self._filter_by_food_trucks(qs, owned_truck_ids)

        # No access for other users
        return qs.none()

    def has_change_permission(self, request, obj=None):
        """Check if user can change this object."""
        if request.user.is_superuser:
            return True

        if obj is None:
            # List view - check if user owns any objects
            return self._user_owns_objects(request)

        return self._user_owns_object(request, obj)

    def has_delete_permission(self, request, obj=None):
        """Check if user can delete this object."""
        if request.user.is_superuser:
            return True

        if obj is None:
            # List view - check if user owns any objects
            return self._user_owns_objects(request)

        return self._user_owns_object(request, obj)

    def has_view_permission(self, request, obj=None):
        """Check if user can view this object."""
        if request.user.is_superuser:
            return True

        if obj is None:
            # List view - check if user owns any objects
            return self._user_owns_objects(request)

        return self._user_owns_object(request, obj)

    def _filter_by_food_trucks(self, qs, truck_ids):
        """
        Filter queryset by food truck IDs.

        This method should be overridden in subclasses to implement
        the specific filtering logic for each model.
        """
        raise NotImplementedError("Subclasses must implement _filter_by_food_trucks")

    def _user_owns_objects(self, request):
        """Check if user owns any objects of this type."""
        if not hasattr(request.user, 'foodtrucks'):
            return False

        owned_truck_ids = request.user.foodtrucks.values_list('id', flat=True)
        if not owned_truck_ids:
            return False

        # Check if there are any objects related to user's food trucks
        qs = self.get_queryset(request)
        return qs.exists()

    def _user_owns_object(self, request, obj):
        """Check if user owns this specific object."""
        if not hasattr(request.user, 'foodtrucks'):
            return False

        owned_truck_ids = request.user.foodtrucks.values_list('id', flat=True)
        return self._object_belongs_to_trucks(obj, owned_truck_ids)

    def _object_belongs_to_trucks(self, obj, truck_ids):
        """
        Check if object belongs to any of the given food truck IDs.

        This method should be overridden in subclasses to implement
        the specific ownership check for each model.
        """
        raise NotImplementedError("Subclasses must implement _object_belongs_to_trucks")


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ('action', 'model', 'object_id', 'created_at', 'user')
    search_fields = ('action', 'model', 'object_id', 'user__email')
    list_filter = ('action', 'model', 'created_at')
    readonly_fields = ('action', 'model', 'object_id', 'payload', 'created_at', 'user')

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Tax)
class TaxAdmin(admin.ModelAdmin):
    list_display = ('name', 'country', 'rate', 'is_active', 'is_default', 'created_at')
    list_filter = ('country', 'is_active', 'is_default', 'created_at')
    search_fields = ('name',)
    readonly_fields = ('created_at',)