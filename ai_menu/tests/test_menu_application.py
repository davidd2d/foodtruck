from decimal import Decimal

from django.test import TestCase

from ai_menu.models import AIRecommendation
from ai_menu.services.menu_application import AIRecommendationMenuApplicationService
from menu.models import Category, Combo, ComboItem, Option, OptionGroup
from menu.tests.factories import CategoryFactory, ItemFactory


class AIRecommendationMenuApplicationServiceTests(TestCase):
    """Tests for applying AI recommendations to menu entities."""

    def setUp(self):
        self.category = CategoryFactory(name='Burgers')
        self.item = ItemFactory(category=self.category, name='Classic Burger', base_price=Decimal('10.00'))
        self.fries = ItemFactory(category=self.category, name='Fries', base_price=Decimal('4.00'))
        self.service = AIRecommendationMenuApplicationService()

    def test_apply_free_option_creates_free_customization(self):
        recommendation = AIRecommendation.objects.create(
            item=self.item,
            recommendation_type='free_option',
            payload={'name': 'Extra pickles', 'reason': 'Adds freshness'},
            status='pending',
        )

        result = self.service.apply_recommendation(recommendation)

        group = OptionGroup.objects.get(category=self.item.category, name='AI Free Customizations')
        option = Option.objects.get(group=group, name='Extra pickles')
        self.assertEqual(option.price_modifier, Decimal('0.00'))
        self.assertTrue(option.items.filter(id=self.item.id).exists())
        self.assertEqual(result['application_status'], 'applied')

    def test_apply_paid_option_creates_add_on(self):
        recommendation = AIRecommendation.objects.create(
            item=self.item,
            recommendation_type='paid_option',
            payload={'name': 'Extra cheddar', 'reason': 'Premium', 'suggested_price': 1.5},
            status='pending',
        )

        result = self.service.apply_recommendation(recommendation)

        group = OptionGroup.objects.get(category=self.item.category, name='AI Paid Add-ons')
        option = Option.objects.get(group=group, name='Extra cheddar')
        self.assertEqual(option.price_modifier, Decimal('1.5'))
        self.assertTrue(option.items.filter(id=self.item.id).exists())
        self.assertEqual(result['application']['group_id'], group.id)
        self.assertEqual(result['application']['option_id'], option.id)

    def test_apply_existing_option_enable_links_item(self):
        group = OptionGroup.objects.create(
            category=self.category,
            name='Existing Paid Options',
            required=False,
            min_choices=0,
        )
        option = Option.objects.create(
            group=group,
            name='Extra truffle sauce',
            price_modifier=Decimal('1.50'),
            is_available=True,
        )

        recommendation = AIRecommendation.objects.create(
            item=self.item,
            recommendation_type='paid_option',
            payload={
                'name': option.name,
                'reason': 'High affinity for this burger',
                'existing_option_id': option.id,
                'suggested_action': 'enable',
                'current_status': 'disabled',
            },
            status='pending',
        )

        result = self.service.apply_recommendation(recommendation)

        self.assertEqual(result['application_status'], 'applied')
        self.assertTrue(option.items.filter(id=self.item.id).exists())
        self.assertEqual(result['application']['action'], 'link_existing_option')

    def test_apply_existing_option_disable_unlinks_item(self):
        group = OptionGroup.objects.create(
            category=self.category,
            name='Existing Free Options',
            required=False,
            min_choices=0,
        )
        option = Option.objects.create(
            group=group,
            name='Extra pickles',
            price_modifier=Decimal('0.00'),
            is_available=True,
        )
        option.items.add(self.item)

        recommendation = AIRecommendation.objects.create(
            item=self.item,
            recommendation_type='free_option',
            payload={
                'name': option.name,
                'reason': 'Low demand for this dish',
                'existing_option_id': option.id,
                'suggested_action': 'disable',
                'current_status': 'enabled',
            },
            status='pending',
        )

        result = self.service.apply_recommendation(recommendation)

        self.assertEqual(result['application_status'], 'applied')
        self.assertFalse(option.items.filter(id=self.item.id).exists())
        self.assertEqual(result['application']['action'], 'unlink_existing_option')

    def test_apply_bundle_requires_manual_review(self):
        recommendation = AIRecommendation.objects.create(
            item=self.item,
            recommendation_type='bundle',
            payload={'name': 'Combo', 'reason': 'Raise basket', 'items': ['Classic Burger', 'Fries']},
            status='pending',
        )

        result = self.service.apply_recommendation(recommendation)

        self.assertEqual(result['application_status'], 'applied')
        combo_category = Category.objects.get(menu=self.item.category.menu, name='Combos')
        combo = Combo.objects.get(category=combo_category, name='Combo')
        combo_items = list(combo.combo_items.order_by('display_order'))
        self.assertEqual(len(combo_items), 2)
        self.assertEqual(combo_items[0].item, self.item)
        self.assertEqual(combo_items[1].item, self.fries)
        self.assertEqual(combo.combo_price, Decimal('14.00'))

    def test_apply_bundle_with_unknown_component_creates_combo_without_price(self):
        recommendation = AIRecommendation.objects.create(
            item=self.item,
            recommendation_type='bundle',
            payload={'name': 'Mystery Combo', 'reason': 'Raise basket', 'items': ['Classic Burger', 'Drink']},
            status='pending',
        )

        result = self.service.apply_recommendation(recommendation)

        combo = Combo.objects.get(name='Mystery Combo')
        self.assertEqual(result['application_status'], 'applied')
        self.assertIsNone(combo.combo_price)
        unresolved_component = combo.combo_items.get(display_name='Drink')
        self.assertIsNone(unresolved_component.item)

    def test_revert_recommendation_removes_created_option_and_empty_group(self):
        recommendation = AIRecommendation.objects.create(
            item=self.item,
            recommendation_type='free_option',
            payload={'name': 'Extra pickles', 'reason': 'Adds freshness'},
            status='pending',
        )

        applied = self.service.apply_recommendation(recommendation)
        recommendation.payload = {**recommendation.payload, **applied}
        recommendation.save(update_fields=['payload'])

        option_id = applied['application']['option_id']
        group_id = applied['application']['group_id']
        revert_result = self.service.revert_recommendation(recommendation)

        self.assertEqual(revert_result['application_status'], 'reverted')
        self.assertFalse(Option.objects.filter(id=option_id).exists())
        self.assertFalse(OptionGroup.objects.filter(id=group_id).exists())

    def test_revert_bundle_recommendation_removes_combo_and_empty_combo_category(self):
        recommendation = AIRecommendation.objects.create(
            item=self.item,
            recommendation_type='bundle',
            payload={'name': 'Combo', 'reason': 'Raise basket', 'items': ['Classic Burger', 'Fries']},
            status='pending',
        )

        applied = self.service.apply_recommendation(recommendation)
        recommendation.payload = {**recommendation.payload, **applied}
        recommendation.save(update_fields=['payload'])

        combo_id = applied['application']['combo_id']
        category_id = applied['application']['category_id']
        revert_result = self.service.revert_recommendation(recommendation)

        self.assertEqual(revert_result['application_status'], 'reverted')
        self.assertFalse(Combo.objects.filter(id=combo_id).exists())
        self.assertFalse(Category.objects.filter(id=category_id).exists())