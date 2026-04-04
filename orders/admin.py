from django.contrib import admin
from common.admin import OwnerRestrictedAdminMixin
from .models import Order, OrderItem, OrderItemOption, PickupSlot


class OrderItemOptionInline(admin.TabularInline):
    model = OrderItemOption
    extra = 0
    readonly_fields = ('option', 'price_modifier')


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ('item', 'quantity', 'unit_price', 'total_price', 'selected_options')
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


# OrderItem and OrderItemOption are managed through inlines, no separate admin needed
# But if needed, they would be restricted too
