from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from common.services import AuditService
from orders.models import Ticket


class TicketService:
    """Generate immutable fiscal tickets from paid order snapshots."""

    @classmethod
    @transaction.atomic
    def generate_ticket(cls, order):
        if not order.is_paid():
            raise ValidationError('Cannot generate a ticket for an unpaid order.')

        if hasattr(order, 'ticket'):
            return order.ticket

        number = cls._next_ticket_number()
        payload = cls._build_payload(order)

        ticket = Ticket.objects.create(
            order=order,
            number=number,
            issued_at=timezone.now(),
            total_amount=order.total_amount,
            tax_amount=order.tax_amount,
            payload=payload,
        )

        AuditService.log(
            'ticket_generated',
            ticket,
            payload={'order_id': order.pk, 'number': ticket.number},
            user=order.user,
        )
        return ticket

    @staticmethod
    def _next_ticket_number():
        last_ticket = Ticket.objects.select_for_update().order_by('-id').first()
        next_value = 1
        if last_ticket is not None:
            try:
                next_value = int(last_ticket.number.split('-')[-1]) + 1
            except (ValueError, IndexError):
                next_value = last_ticket.id + 1
        return f"TCK-{timezone.now().year}-{next_value:06d}"

    @staticmethod
    def _build_payload(order):
        items_payload = []
        for line in order.items.select_related('item', 'combo').prefetch_related('selected_options__option').order_by('id'):
            entry = {
                'product_name': line.product_name,
                'line_type': line.line_type,
                'quantity': line.quantity,
                'unit_price': str(line.unit_price),
                'tax_rate': str(line.tax_rate),
                'tax_amount': str(line.tax_amount),
                'total_price': str(line.total_price),
            }
            if line.combo_id and line.options:
                entry['combo_components'] = line.options
            items_payload.append(entry)

        return {
            'order_id': order.pk,
            'issued_at': timezone.now().isoformat(),
            'currency': order.currency,
            'total_amount': str(order.total_amount),
            'tax_amount': str(order.tax_amount),
            'food_truck_id': order.food_truck_id,
            'items': items_payload,
        }
