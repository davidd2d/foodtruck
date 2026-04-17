import csv
import io
from datetime import datetime

from common.services import AuditService
from orders.models import Order


class AccountingExportService:
    @staticmethod
    def export_orders_csv(start_date, end_date, user=None, owner=None, food_truck=None):
        if isinstance(start_date, datetime):
            start_date = start_date.date()
        if isinstance(end_date, datetime):
            end_date = end_date.date()

        queryset = Order.objects.filter(
            paid_at__date__gte=start_date,
            paid_at__date__lte=end_date,
            paid_at__isnull=False,
            payment__status='paid',
        ).select_related('ticket', 'payment').order_by('paid_at', 'id')

        if owner is not None:
            queryset = queryset.filter(food_truck__owner=owner)
        if food_truck is not None:
            queryset = queryset.filter(food_truck=food_truck)

        buffer = io.StringIO()
        writer = csv.writer(buffer)
        writer.writerow([
            'order_id',
            'food_truck_slug',
            'ticket_number',
            'date',
            'total_amount',
            'tax_amount',
            'payment_status',
            'stripe_connect_account_id',
        ])

        exported_order_ids = []
        for order in queryset:
            writer.writerow([
                order.id,
                order.food_truck.slug,
                getattr(getattr(order, 'ticket', None), 'number', ''),
                order.paid_at.isoformat() if order.paid_at else '',
                str(order.total_amount),
                str(order.tax_amount),
                order.payment.status,
                getattr(order.food_truck, 'stripe_connect_account_id', '') or '',
            ])
            exported_order_ids.append(order.id)

        AuditService.log_custom(
            'accounting_export_generated',
            'AccountingExport',
            f'{start_date}_{end_date}',
            payload={
                'start_date': str(start_date),
                'end_date': str(end_date),
                'order_ids': exported_order_ids,
                'food_truck_id': getattr(food_truck, 'id', None),
                'owner_id': getattr(owner, 'id', None),
            },
            user=user,
        )
        return buffer.getvalue()