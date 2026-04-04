from django.contrib import admin
from common.admin import OwnerRestrictedAdminMixin
from .models import FoodTruck, Plan, Subscription


@admin.register(FoodTruck)
class FoodTruckAdmin(OwnerRestrictedAdminMixin, admin.ModelAdmin):
    list_display = ('name', 'owner', 'is_active', 'get_plan')
    search_fields = ('name',)
    list_filter = ('is_active',)
    autocomplete_fields = ('owner', 'supported_preferences')

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related('owner', 'subscription__plan').prefetch_related('supported_preferences')

    def get_plan(self, obj):
        return obj.get_plan().name if obj.get_plan() else 'No Plan'
    get_plan.short_description = 'Plan'

    def save_model(self, request, obj, form, change):
        """Automatically assign owner if not set."""
        if not obj.owner_id:
            obj.owner = request.user
        super().save_model(request, obj, form, change)

    def _filter_by_food_trucks(self, qs, truck_ids):
        """FoodTruck filtering - return trucks owned by user."""
        return qs.filter(id__in=truck_ids)

    def _object_belongs_to_trucks(self, obj, truck_ids):
        """Check if this FoodTruck belongs to user's trucks."""
        return obj.id in truck_ids


@admin.register(Plan)
class PlanAdmin(admin.ModelAdmin):
    """Plan admin - only superusers can manage plans."""
    list_display = ('name', 'code', 'price', 'allows_ordering')
    search_fields = ('name', 'code')
    list_filter = ('allows_ordering',)

    def has_view_permission(self, request, obj=None):
        return request.user.is_superuser

    def has_change_permission(self, request, obj=None):
        return request.user.is_superuser

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser


@admin.register(Subscription)
class SubscriptionAdmin(OwnerRestrictedAdminMixin, admin.ModelAdmin):
    """Subscription admin - owners can see their subscriptions."""
    list_display = ('food_truck', 'plan', 'status', 'start_date', 'end_date')
    search_fields = ('food_truck__name', 'plan__name')
    list_filter = ('status', 'plan')
    autocomplete_fields = ('food_truck', 'plan')

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related('food_truck', 'plan')

    def _filter_by_food_trucks(self, qs, truck_ids):
        """Filter subscriptions by food truck ownership."""
        return qs.filter(food_truck_id__in=truck_ids)

    def _object_belongs_to_trucks(self, obj, truck_ids):
        """Check if subscription's food truck belongs to user."""
        return obj.food_truck_id in truck_ids
