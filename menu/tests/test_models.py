from decimal import Decimal
from django.core.exceptions import ValidationError
from django.test import TestCase
from menu.tests.factories import (
    MenuFactory,
    CategoryFactory,
    ItemFactory,
    OptionGroupFactory,
    OptionFactory,
)


class ItemModelTests(TestCase):
    def setUp(self):
        self.category = CategoryFactory()
        self.item = ItemFactory(category=self.category, base_price=Decimal('10.00'))

    def test_is_available_now_returns_boolean(self):
        self.assertTrue(self.item.is_available_now())
        self.item.is_available = False
        self.item.save()
        self.assertFalse(self.item.is_available_now())

    def test_get_price_with_options_includes_price_modifiers(self):
        option_group = OptionGroupFactory(item=self.item, min_choices=0, max_choices=2)
        option = OptionFactory(group=option_group, price_modifier=Decimal('2.75'))

        total_price = self.item.get_price_with_options([option.id])
        self.assertEqual(total_price, Decimal('12.75'))

    def test_invalid_option_selection_raises_validation_error(self):
        option_group = OptionGroupFactory(item=self.item, min_choices=1, max_choices=1)
        with self.assertRaises(ValidationError):
            self.item.get_price_with_options([])

    def test_validate_options_rejects_out_of_scope_option(self):
        other_item = ItemFactory(base_price=Decimal('5.00'))
        option_group = OptionGroupFactory(item=other_item, min_choices=0, max_choices=1)
        option = OptionFactory(group=option_group, price_modifier=Decimal('1.00'))

        with self.assertRaises(ValidationError):
            self.item.validate_options([option.id])
