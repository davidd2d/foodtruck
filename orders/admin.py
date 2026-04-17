from django.contrib import admin
from django.contrib import messages
from django.utils.translation import gettext_lazy as _
from common.admin import OwnerRestrictedAdminMixin
from .models import Location, Order, OrderItem, OrderItemOption, PickupSlot, ServiceSchedule, Ticket


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
    readonly_fields = ('item', 'combo', 'quantity', 'unit_price', 'tax_rate', 'tax_amount', 'total_price')
    inlines = [OrderItemOptionInline]


@admin.register(Order)
class OrderAdmin(OwnerRestrictedAdminMixin, admin.ModelAdmin):
    list_display = ('id', 'user', 'customer_email', 'food_truck', 'status', 'is_anonymized', 'total_amount', 'tax_amount', 'paid_at', 'created_at')
    search_fields = ('id', 'user__email', 'customer_email', 'food_truck__name')
    list_filter = ('status', 'food_truck', 'is_anonymized', 'created_at', 'paid_at')
    readonly_fields = (
        'customer_name',
        'customer_email',
        'customer_phone',
        'is_anonymized',
        'anonymized_at',
        'total_price',
        'total_amount',
        'tax_amount',
        'currency',
        'paid_at',
    )
    inlines = [OrderItemInline]
    actions = ['anonymize_selected_orders']

    @admin.action(description='Anonymize selected orders')
    def anonymize_selected_orders(self, request, queryset):
        anonymized = 0
        for order in queryset:
            if order.is_paid() and not order.is_anonymized:
                order.anonymize()
                anonymized += 1
        self.message_user(request, f'{anonymized} order(s) anonymized.', level=messages.SUCCESS)

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


@admin.register(Ticket)
class TicketAdmin(OwnerRestrictedAdminMixin, admin.ModelAdmin):
    list_display = ('number', 'order', 'total_amount', 'tax_amount', 'issued_at')
    search_fields = ('number', 'order__id', 'order__user__email', 'order__food_truck__name')
    list_filter = ('issued_at',)
    readonly_fields = ('order', 'number', 'issued_at', 'total_amount', 'tax_amount', 'payload')

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related('order__food_truck', 'order__user')

    def _filter_by_food_trucks(self, qs, truck_ids):
        return qs.filter(order__food_truck_id__in=truck_ids)

    def _object_belongs_to_trucks(self, obj, truck_ids):
        return obj.order.food_truck_id in truck_ids
