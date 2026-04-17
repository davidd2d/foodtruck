from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from orders.models import Order


class DataRetentionService:
    @staticmethod
    def get_orders_to_anonymize(days=90):
        cutoff = timezone.now() - timedelta(days=days)
        return Order.objects.filter(
            paid_at__isnull=False,
            paid_at__lte=cutoff,
            is_anonymized=False,
        ).order_by('paid_at')

    @classmethod
    def anonymize_old_orders(cls, days=90, batch_size=500):
        anonymized_count = 0
        queryset = cls.get_orders_to_anonymize(days=days).values_list('pk', flat=True)[:batch_size]
        for order_id in queryset:
            with transaction.atomic():
                order = Order.objects.select_for_update().get(pk=order_id)
                if order.is_anonymized or not order.is_paid():
                    continue
                order.anonymize()
                anonymized_count += 1
        return anonymized_count