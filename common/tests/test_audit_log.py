from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase

from common.models import AuditLog
from orders.models import Order
from orders.tests.factories import CategoryFactory, ItemFactory, MenuFactory, OrderFactory, TaxFactory
from payments.tests.factories import PaymentFactory


class AuditLogComplianceTests(TestCase):
    def _build_paid_order(self, suffix):
        tax = TaxFactory(rate=Decimal('0.1000'))
        order = OrderFactory(status=Order.Status.DRAFT)
        menu = MenuFactory(food_truck=order.food_truck)
        category = CategoryFactory(menu=menu)
        item = ItemFactory(category=category, name=f'Audit Item {suffix}', base_price=Decimal('10.00'), tax=tax)
        order.add_item(item, quantity=1)
        order.submit()

        payment = PaymentFactory(order=order, amount=order.total_price, stripe_session_id=f'sess_audit_{suffix}')
        payment.mark_as_paid(payment_intent_id=f'pi_audit_{suffix}')
        order.refresh_from_db()
        return order

    def test_audit_log_created_on_payment(self):
        order = self._build_paid_order('payment')

        self.assertTrue(
            AuditLog.objects.filter(
                action='payment_success',
                model='Payment',
                payload__order_id=order.id,
            ).exists()
        )
        self.assertTrue(
            AuditLog.objects.filter(
                action='order_paid',
                model='Order',
                object_id=str(order.id),
            ).exists()
        )

    def test_audit_log_created_on_ticket_generation(self):
        order = self._build_paid_order('ticket')

        self.assertTrue(
            AuditLog.objects.filter(
                action='ticket_generated',
                model='Ticket',
                payload__order_id=order.id,
            ).exists()
        )

    def test_attempt_to_modify_paid_order_logs_event(self):
        order = self._build_paid_order('immutability')

        with self.assertRaises(ValidationError):
            order.assert_mutable()

        self.assertTrue(
            AuditLog.objects.filter(
                action='order_modification_blocked',
                model='Order',
                object_id=str(order.id),
            ).exists()
        )
