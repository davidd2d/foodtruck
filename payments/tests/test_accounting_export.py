import csv
import io
from datetime import timedelta
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone

from common.models import AuditLog
from orders.models import Order
from orders.tests.factories import CategoryFactory, ItemFactory, MenuFactory, OrderFactory
from payments.services.accounting_export_service import AccountingExportService
from payments.tests.factories import PaymentFactory


class AccountingExportServiceTests(TestCase):
    def _build_order(self, suffix='export', paid=True):
        order = OrderFactory(status='draft')
        menu = MenuFactory(food_truck=order.food_truck)
        category = CategoryFactory(menu=menu)
        item = ItemFactory(category=category, name=f'Export Item {suffix}', base_price=Decimal('10.00'))
        order.add_item(item, quantity=1)
        order.submit()

        payment = PaymentFactory(order=order, amount=order.total_price, stripe_session_id=f'sess_export_{suffix}')
        if paid:
            payment.mark_as_paid(payment_intent_id=f'pi_export_{suffix}')
            order.refresh_from_db()
            Order.objects.filter(pk=order.pk).update(paid_at=timezone.now() - timedelta(days=1))
            order.refresh_from_db()
        return order

    def test_export_contains_only_paid_orders(self):
        paid_order = self._build_order('paid', paid=True)
        self._build_order('draft', paid=False)

        csv_content = AccountingExportService.export_orders_csv(timezone.localdate() - timedelta(days=7), timezone.localdate())

        self.assertIn(str(paid_order.id), csv_content)
        self.assertNotIn('draft', csv_content)

    def test_export_uses_stored_values(self):
        order = self._build_order('stored', paid=True)
        original_total = str(order.total_amount)
        original_tax = str(order.tax_amount)
        order.items.update(total_price=Decimal('999.99'))

        csv_content = AccountingExportService.export_orders_csv(timezone.localdate() - timedelta(days=7), timezone.localdate())
        rows = list(csv.DictReader(io.StringIO(csv_content)))
        exported = next(row for row in rows if row['order_id'] == str(order.id))

        self.assertEqual(exported['total_amount'], original_total)
        self.assertEqual(exported['tax_amount'], original_tax)

    def test_export_format_is_valid_csv(self):
        order = self._build_order('format', paid=True)

        csv_content = AccountingExportService.export_orders_csv(timezone.localdate() - timedelta(days=7), timezone.localdate())
        rows = list(csv.DictReader(io.StringIO(csv_content)))

        self.assertTrue(rows)
        self.assertEqual(rows[0]['order_id'], str(order.id))
        self.assertEqual(rows[0]['ticket_number'], order.ticket.number)
        self.assertEqual(rows[0]['payment_status'], 'paid')
        self.assertTrue(
            AuditLog.objects.filter(action='accounting_export_generated', model='AccountingExport').exists()
        )