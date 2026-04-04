from django.contrib import admin
from common.admin import OwnerRestrictedAdminMixin
from .models import Payment


@admin.register(Payment)
class PaymentAdmin(OwnerRestrictedAdminMixin, admin.ModelAdmin):
    """Payment admin - superusers can manage all, owners can see payments for their orders."""
    list_display = ('order', 'amount', 'currency', 'status', 'provider', 'created_at')
    search_fields = ('order__id', 'provider_payment_id')
    list_filter = ('status', 'provider', 'currency', 'created_at')
    readonly_fields = ('amount', 'currency', 'provider_payment_id', 'created_at', 'updated_at')

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related('order__food_truck')

    def _filter_by_food_trucks(self, qs, truck_ids):
        """Filter payments by food truck ownership (through order)."""
        return qs.filter(order__food_truck_id__in=truck_ids)

    def _object_belongs_to_trucks(self, obj, truck_ids):
        """Check if payment's order's food truck belongs to user."""
        return obj.order.food_truck_id in truck_ids
