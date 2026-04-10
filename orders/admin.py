from django.contrib import admin
from django.utils.translation import gettext_lazy as _
from common.admin import OwnerRestrictedAdminMixin
from .models import Location, Order, OrderItem, OrderItemOption, PickupSlot, ServiceSchedule


class ActiveLocationFilter(admin.SimpleListFilter):
    title = _('Location')
    parameter_name = 'location'

    def lookups(self, request, model_admin):
        locations = Location.objects.filter(is_active=True).select_related('food_truck')
        choices = [(loc.id, str(loc)) for loc in locations]
        choices.insert(0, ('null', _('No location (base)')))  # Option for null location
        return choices

    def queryset(self, request, queryset):
        if self.value() == 'null':
            return queryset.filter(location__isnull=True)
        elif self.value():
            return queryset.filter(location_id=self.value())
        return queryset


class OrderItemOptionInline(admin.TabularInline):
    model = OrderItemOption
    extra = 0
    readonly_fields = ('option', 'price_modifier')


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ('item', 'quantity', 'unit_price', 'total_price')
    inlines = [OrderItemOptionInline]


@admin.register(Order)
class OrderAdmin(OwnerRestrictedAdminMixin, admin.ModelAdmin):
    list_display = ('id', 'user', 'food_truck', 'status', 'total_price', 'created_at')
    search_fields = ('id', 'user__email', 'food_truck__name')
    list_filter = ('status', 'food_truck', 'created_at')
    readonly_fields = ('total_price',)
    inlines = [OrderItemInline]

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related('user', 'food_truck', 'pickup_slot').prefetch_related('items__selected_options')

    def _filter_by_food_trucks(self, qs, truck_ids):
        """Filter orders by food truck ownership."""
        return qs.filter(food_truck_id__in=truck_ids)

    def _object_belongs_to_trucks(self, obj, truck_ids):
        """Check if order's food truck belongs to user."""
        return obj.food_truck_id in truck_ids


@admin.register(PickupSlot)
class PickupSlotAdmin(OwnerRestrictedAdminMixin, admin.ModelAdmin):
    list_display = ('food_truck', 'start_time', 'end_time', 'capacity', 'current_orders_count', 'remaining_capacity')
    search_fields = ('food_truck__name',)
    list_filter = ('food_truck', 'start_time')
    readonly_fields = ('current_orders_count', 'remaining_capacity')

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related('food_truck')

    def _filter_by_food_trucks(self, qs, truck_ids):
        """Filter pickup slots by food truck ownership."""
        return qs.filter(food_truck_id__in=truck_ids)

    def _object_belongs_to_trucks(self, obj, truck_ids):
        """Check if pickup slot's food truck belongs to user."""
        return obj.food_truck_id in truck_ids


@admin.register(Location)
class LocationAdmin(OwnerRestrictedAdminMixin, admin.ModelAdmin):
    list_display = ('food_truck', 'name', 'city', 'postal_code', 'is_active')
    search_fields = ('food_truck__name', 'city', 'postal_code', 'address_line_1')
    list_filter = ('is_active', 'city', 'country')
    readonly_fields = ('created_at', 'updated_at')

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('food_truck', 'service_schedule')

    def _filter_by_food_trucks(self, qs, truck_ids):
        return qs.filter(food_truck_id__in=truck_ids)

    def _object_belongs_to_trucks(self, obj, truck_ids):
        return obj.food_truck_id in truck_ids


@admin.register(ServiceSchedule)
class ServiceScheduleAdmin(OwnerRestrictedAdminMixin, admin.ModelAdmin):
    list_display = ('food_truck', 'location', 'day_of_week', 'start_time', 'end_time', 'capacity_per_slot', 'slot_duration_minutes', 'is_active')
    list_filter = ('food_truck', ActiveLocationFilter, 'day_of_week', 'is_active')
    search_fields = ('food_truck__name', 'location__name', 'location__city', 'location__postal_code')
    readonly_fields = ('created_at', 'updated_at')
    fieldsets = (
        (None, {
            'fields': ('food_truck', 'location', 'day_of_week', 'start_time', 'end_time', 'capacity_per_slot', 'slot_duration_minutes', 'is_active')
        }),
        (_('Metadata'), {
            'fields': ('created_at', 'updated_at'),
        }),
    )

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related('food_truck')

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == 'location':
            kwargs['queryset'] = Location.objects.filter(is_active=True)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def _filter_by_food_trucks(self, qs, truck_ids):
        return qs.filter(food_truck_id__in=truck_ids)

    def _object_belongs_to_trucks(self, obj, truck_ids):
        return obj.food_truck_id in truck_ids


# OrderItem and OrderItemOption are managed through inlines, no separate admin needed
# But if needed, they would be restricted too
