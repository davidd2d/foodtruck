from django.contrib import admin
from common.admin import OwnerRestrictedAdminMixin
from .models import Payment, StripeEvent


@admin.register(Payment)
class PaymentAdmin(OwnerRestrictedAdminMixin, admin.ModelAdmin):
    """Payment admin - superusers can manage all, owners can see payments for their orders."""
    list_display = ('order', 'amount', 'status', 'provider', 'stripe_session_id', 'stripe_connect_account_id', 'transfer_group', 'paid_at', 'created_at')
    search_fields = ('order__id', 'stripe_session_id', 'stripe_payment_intent', 'stripe_connect_account_id', 'transfer_group')
    list_filter = ('status', 'provider', 'created_at', 'paid_at')
    readonly_fields = (
        'amount',
        'provider',
        'stripe_session_id',
        'stripe_payment_intent',
        'stripe_connect_account_id',
        'transfer_group',
        'paid_at',
        'created_at',
        'updated_at',
    )

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related('order__food_truck')

    def _filter_by_food_trucks(self, qs, truck_ids):
        """Filter payments by food truck ownership (through order)."""
        return qs.filter(order__food_truck_id__in=truck_ids)

    def _object_belongs_to_trucks(self, obj, truck_ids):
        """Check if payment's order's food truck belongs to user."""
        return obj.order.food_truck_id in truck_ids


@admin.register(StripeEvent)
class StripeEventAdmin(admin.ModelAdmin):
    list_display = ('stripe_event_id', 'type', 'processed_at')
    search_fields = ('stripe_event_id', 'type')
    readonly_fields = ('stripe_event_id', 'type', 'processed_at')
