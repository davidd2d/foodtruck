from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase

from orders.models import Order
from orders.services.ticket_service import TicketService
from orders.tests.factories import CategoryFactory, ItemFactory, MenuFactory, OrderFactory
from payments.tests.factories import PaymentFactory


class OrderFinancialComplianceTests(TestCase):
    def _build_submitted_order(self, unit_price=Decimal('10.00'), quantity=2, tax_rate=Decimal('0.1000')):
        order = OrderFactory(status=Order.Status.DRAFT)
        menu = MenuFactory(food_truck=order.food_truck)
        category = CategoryFactory(menu=menu)
        item = ItemFactory(category=category, base_price=unit_price)
        order.add_item(item, quantity=quantity)
        line = order.items.first()
        line.tax_rate = tax_rate
        line.save(update_fields=['tax_rate'])
        order.submit()
        return order

    def test_order_financials_are_frozen_after_payment(self):
        order = self._build_submitted_order()
        payment = PaymentFactory(order=order, amount=order.total_price)

        payment.mark_as_paid(payment_intent_id='pi_freeze')

        order.refresh_from_db()
        self.assertIsNotNone(order.paid_at)
        self.assertEqual(order.total_amount, Decimal('22.00'))
        self.assertEqual(order.tax_amount, Decimal('2.00'))
        self.assertEqual(order.currency, 'EUR')

    def test_order_cannot_change_total_after_payment(self):
        order = self._build_submitted_order()
        payment = PaymentFactory(order=order, amount=order.total_price)
        payment.mark_as_paid(payment_intent_id='pi_immutable_total')

        order.total_amount = Decimal('99.99')
        with self.assertRaises(ValidationError):
            order.save()

    def test_order_item_tax_is_stored(self):
        order = self._build_submitted_order(unit_price=Decimal('5.00'), quantity=2, tax_rate=Decimal('0.2000'))
        item = order.items.first()

        self.assertEqual(item.tax_amount, Decimal('2.00'))
        self.assertEqual(item.total_price, Decimal('12.00'))

    def test_order_item_not_recomputed_after_payment(self):
        order = self._build_submitted_order(unit_price=Decimal('5.00'), quantity=2, tax_rate=Decimal('0.2000'))
        line = order.items.first()
        payment = PaymentFactory(order=order, amount=order.total_price)
        payment.mark_as_paid(payment_intent_id='pi_item_lock')

        line.unit_price = Decimal('100.00')
        with self.assertRaises(ValidationError):
            line.save()

        line.refresh_from_db()
        self.assertEqual(line.total_price, Decimal('12.00'))
        self.assertEqual(line.tax_amount, Decimal('2.00'))


class TicketComplianceTests(TestCase):
    def _build_paid_order(self, suffix):
        order = OrderFactory(status=Order.Status.DRAFT)
        menu = MenuFactory(food_truck=order.food_truck)
        category = CategoryFactory(menu=menu)
        item = ItemFactory(category=category, name=f'Item {suffix}', base_price=Decimal('10.00'))
        order.add_item(item, quantity=1)
        line = order.items.first()
        line.tax_rate = Decimal('0.1000')
        line.save(update_fields=['tax_rate'])
        order.submit()
        payment = PaymentFactory(order=order, amount=order.total_price, stripe_session_id=f'sess_ticket_{suffix}')
        payment.mark_as_paid(payment_intent_id=f'pi_ticket_{suffix}')
        order.refresh_from_db()
        return order

    def test_ticket_generated_after_payment(self):
        order = self._build_paid_order('a')
        self.assertTrue(hasattr(order, 'ticket'))
        self.assertEqual(order.ticket.total_amount, order.total_amount)

    def test_ticket_is_unique(self):
        order = self._build_paid_order('b')
        first_ticket = order.ticket
        second_ticket = TicketService.generate_ticket(order)

        self.assertEqual(first_ticket.pk, second_ticket.pk)

    def test_ticket_number_is_sequential(self):
        order1 = self._build_paid_order('c1')
        order2 = self._build_paid_order('c2')

        n1 = int(order1.ticket.number.split('-')[-1])
        n2 = int(order2.ticket.number.split('-')[-1])
        self.assertEqual(n2, n1 + 1)

    def test_ticket_payload_is_snapshot(self):
        order = self._build_paid_order('d')
        payload = order.ticket.payload

        self.assertEqual(payload['order_id'], order.id)
        self.assertEqual(payload['currency'], order.currency)
        self.assertEqual(payload['total_amount'], str(order.total_amount))
        self.assertTrue(len(payload['items']) >= 1)

    def test_cannot_modify_order_after_payment(self):
        order = self._build_paid_order('e')
        order.tax_amount = Decimal('0.00')

        with self.assertRaises(ValidationError):
            order.save()

    def test_cannot_modify_order_item_after_payment(self):
        order = self._build_paid_order('f')
        line = order.items.first()
        line.quantity = 99

        with self.assertRaises(ValidationError):
            line.save()
