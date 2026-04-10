from decimal import Decimal

from django.db import transaction

from menu.models import Category, Combo, ComboItem, Item, Option, OptionGroup


class AIRecommendationMenuApplicationService:
    """Apply AI recommendations to menu structures when possible."""

    FREE_OPTION_GROUP_NAME = 'AI Free Customizations'
    PAID_OPTION_GROUP_NAME = 'AI Paid Add-ons'
    COMBO_CATEGORY_NAME = 'Combos'

    @transaction.atomic
    def apply_recommendation(self, recommendation):
        """Apply a recommendation to the menu domain and return metadata to persist."""
        if recommendation.recommendation_type == 'free_option':
            return self._create_option(recommendation, self.FREE_OPTION_GROUP_NAME, Decimal('0.00'))

        if recommendation.recommendation_type == 'paid_option':
            suggested_price = recommendation.payload.get('suggested_price') or 0
            return self._create_option(
                recommendation,
                self.PAID_OPTION_GROUP_NAME,
                Decimal(str(suggested_price)),
            )

        if recommendation.recommendation_type == 'bundle':
            return self._create_combo(recommendation)

        return {
            'application_status': 'manual_review_required',
            'application_summary': 'No automatic menu entity was created for this recommendation type.',
        }

    @transaction.atomic
    def revert_recommendation(self, recommendation):
        """Revert a previously applied recommendation back to pending state when possible."""
        application = (recommendation.payload or {}).get('application') or {}
        option_id = application.get('option_id')
        group_id = application.get('group_id')
        combo_id = application.get('combo_id')
        category_id = application.get('category_id')

        if option_id:
            option = Option.objects.filter(id=option_id, group__item=recommendation.item).first()
            if option:
                option.delete()

        if group_id:
            group = OptionGroup.objects.filter(id=group_id, item=recommendation.item).first()
            if group and not group.options.exists():
                group.delete()

        if combo_id:
            combo = Combo.objects.filter(id=combo_id).first()
            if combo:
                combo.delete()

        if category_id:
            category = Category.objects.filter(id=category_id, menu=recommendation.item.category.menu).first()
            if category and not category.items.exists() and not category.combos.exists():
                category.delete()

        return {
            'application_status': 'reverted',
            'application_summary': 'Applied menu entities were removed and the recommendation is pending again.',
        }

    def _create_option(self, recommendation, group_name, price_modifier):
        item = recommendation.item
        payload = recommendation.payload or {}
        option_name = payload.get('name', '').strip()

        group, _ = OptionGroup.objects.get_or_create(
            item=item,
            name=group_name,
            defaults={
                'required': False,
                'min_choices': 0,
                'max_choices': None,
            },
        )

        option, _ = Option.objects.update_or_create(
            group=group,
            name=option_name,
            defaults={
                'price_modifier': price_modifier,
                'is_available': True,
            },
        )

        return {
            'application_status': 'applied',
            'application_summary': 'Menu option created from AI recommendation.',
            'application': {
                'group_id': group.id,
                'group_name': group.name,
                'option_id': option.id,
                'option_name': option.name,
            },
        }

    def _create_combo(self, recommendation):
        item = recommendation.item
        menu = item.category.menu
        payload = recommendation.payload or {}
        combo_name = payload.get('name', '').strip()
        component_names = payload.get('items', []) or []

        category, _ = Category.objects.get_or_create(
            menu=menu,
            name=self.COMBO_CATEGORY_NAME,
            defaults={'display_order': 999},
        )

        combo = Combo.objects.create(
            category=category,
            name=combo_name,
            description=payload.get('reason', ''),
            combo_price=self._infer_combo_price(menu, component_names),
            is_available=True,
        )

        for index, component_name in enumerate(component_names):
            resolved_item = self._resolve_menu_item(menu, component_name)
            ComboItem.objects.create(
                combo=combo,
                item=resolved_item,
                display_name=component_name,
                quantity=1,
                display_order=index,
            )

        summary = 'Combo created from AI recommendation.'
        if combo.combo_price is None:
            summary = 'Combo created from AI recommendation. Price needs manual confirmation.'

        return {
            'application_status': 'applied',
            'application_summary': summary,
            'application': {
                'category_id': category.id,
                'category_name': category.name,
                'combo_id': combo.id,
                'combo_name': combo.name,
            },
        }

    def _resolve_menu_item(self, menu, component_name):
        normalized = (component_name or '').strip()
        if not normalized:
            return None
        return Item.objects.filter(category__menu=menu, name__iexact=normalized).order_by('id').first()

    def _infer_combo_price(self, menu, component_names):
        resolved_items = []
        for component_name in component_names:
            resolved_item = self._resolve_menu_item(menu, component_name)
            if not resolved_item:
                return None
            resolved_items.append(resolved_item)

        if not resolved_items:
            return None

        total = Decimal('0.00')
        for resolved_item in resolved_items:
            total += resolved_item.base_price
        return total