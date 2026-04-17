from decimal import Decimal

from django.test import TestCase

from common.models import Tax
from orders.tests.factories import CategoryFactory, ItemFactory, MenuFactory, OrderFactory, TaxFactory


class OrderItemTaxComplianceTests(TestCase):
    def setUp(self):
        self.default_tax = TaxFactory(rate=Decimal('0.1000'), is_default=True)

    def test_order_item_stores_tax_rate(self):
        order = OrderFactory(status='draft')
        menu = MenuFactory(food_truck=order.food_truck)
        category = CategoryFactory(menu=menu)
        item_tax = TaxFactory(name='TVA 20%', rate=Decimal('0.2000'), is_default=False)
        item = ItemFactory(category=category, base_price=Decimal('10.00'), tax=item_tax)

        order.add_item(item, quantity=2)

        line = order.items.get()
        self.assertEqual(line.tax_rate, Decimal('0.2000'))
        self.assertEqual(line.tax_amount, Decimal('4.00'))
        self.assertEqual(line.total_price, Decimal('24.00'))

    def test_order_item_tax_not_recomputed(self):
        order = OrderFactory(status='draft')
        menu = MenuFactory(food_truck=order.food_truck)
        category = CategoryFactory(menu=menu)
        item_tax = TaxFactory(name='TVA 20%', rate=Decimal('0.2000'), is_default=False)
        item = ItemFactory(category=category, base_price=Decimal('10.00'), tax=item_tax)

        order.add_item(item, quantity=1)
        line = order.items.get()

        item_tax.rate = Decimal('0.0550')
        item_tax.save(update_fields=['rate'])
        line.quantity = 2
        line.save(update_fields=['quantity'])

        line.refresh_from_db()
        self.assertEqual(line.tax_rate, Decimal('0.2000'))
        self.assertEqual(line.tax_amount, Decimal('4.00'))
        self.assertEqual(line.total_price, Decimal('24.00'))

    def test_default_tax_is_used_when_missing(self):
        order = OrderFactory(status='draft')
        menu = MenuFactory(food_truck=order.food_truck)
        category = CategoryFactory(menu=menu)
        item = ItemFactory(category=category, base_price=Decimal('8.00'), tax=None)
        item.tax = None
        item.save(update_fields=['tax'])

        order.add_item(item, quantity=1)

        line = order.items.get()
        self.assertEqual(line.tax_rate, self.default_tax.rate)
        self.assertEqual(line.tax_amount, Decimal('0.80'))
        self.assertEqual(line.total_price, Decimal('8.80'))