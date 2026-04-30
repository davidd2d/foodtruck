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
            if (recommendation.payload or {}).get('existing_option_id'):
                return self._apply_existing_option_recommendation(recommendation)
            return self._create_option(recommendation, self.FREE_OPTION_GROUP_NAME, Decimal('0.00'))

        if recommendation.recommendation_type == 'paid_option':
            if (recommendation.payload or {}).get('existing_option_id'):
                return self._apply_existing_option_recommendation(recommendation)
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
        action = application.get('action')
        option_id = application.get('option_id')
        group_id = application.get('group_id')
        combo_id = application.get('combo_id')
        category_id = application.get('category_id')

        if option_id:
            option = Option.objects.filter(id=option_id, group__category=recommendation.item.category).first()
            if option:
                self._revert_option_application(option, recommendation.item, application, action)

        if group_id and application.get('group_created', False):
            group = OptionGroup.objects.filter(id=group_id, category=recommendation.item.category).first()
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

    def _revert_option_application(self, option, item, application, action):
        """Restore state for applied option-related recommendations."""
        if action == 'link_existing_option':
            if not application.get('previous_item_assignment', False):
                option.items.remove(item)
            return

        if action == 'unlink_existing_option':
            if application.get('previous_item_assignment', True):
                option.items.add(item)
            previous_is_available = application.get('previous_option_is_available')
            if previous_is_available is not None and option.is_available != previous_is_available:
                option.is_available = previous_is_available
                option.save(update_fields=['is_available'])
            return

        if action == 'create_option':
            if application.get('option_created', False):
                option.delete()
                return

            previous_price_modifier = application.get('previous_price_modifier')
            previous_option_is_available = application.get('previous_option_is_available')
            previous_item_assignment = application.get('previous_item_assignment', False)

            update_fields = []
            if previous_price_modifier is not None and option.price_modifier != Decimal(str(previous_price_modifier)):
                option.price_modifier = Decimal(str(previous_price_modifier))
                update_fields.append('price_modifier')
            if previous_option_is_available is not None and option.is_available != previous_option_is_available:
                option.is_available = previous_option_is_available
                update_fields.append('is_available')
            if update_fields:
                option.save(update_fields=update_fields)

            if previous_item_assignment:
                option.items.add(item)
            else:
                option.items.remove(item)

    def _create_option(self, recommendation, group_name, price_modifier):
        item = recommendation.item
        payload = recommendation.payload or {}
        option_name = payload.get('name', '').strip()

        existing_option = Option.objects.filter(
            group__category=item.category,
            name__iexact=option_name,
        ).select_related('group').first()

        if existing_option is not None:
            previous_item_assignment = existing_option.items.filter(pk=item.pk).exists()
            previous_option_is_available = existing_option.is_available
            if not existing_option.is_available:
                existing_option.is_available = True
                existing_option.save(update_fields=['is_available'])
            existing_option.items.add(item)
            return {
                'application_status': 'applied',
                'application_summary': 'Existing category option reused and linked to this item.',
                'application': {
                    'action': 'link_existing_option',
                    'group_id': existing_option.group_id,
                    'group_name': existing_option.group.name,
                    'option_id': existing_option.id,
                    'option_name': existing_option.name,
                    'group_created': False,
                    'option_created': False,
                    'previous_item_assignment': previous_item_assignment,
                    'previous_option_is_available': previous_option_is_available,
                    'previous_price_modifier': str(existing_option.price_modifier),
                },
            }

        group, group_created = OptionGroup.objects.get_or_create(
            category=item.category,
            name=group_name,
            defaults={
                'required': False,
                'min_choices': 0,
                'max_choices': None,
            },
        )

        option = Option.objects.filter(group=group, name=option_name).first()
        option_created = option is None
        previous_item_assignment = False
        previous_option_is_available = None
        previous_price_modifier = None

        if option_created:
            option = Option.objects.create(
                group=group,
                name=option_name,
                price_modifier=price_modifier,
                is_available=True,
            )
        else:
            previous_item_assignment = option.items.filter(pk=item.pk).exists()
            previous_option_is_available = option.is_available
            previous_price_modifier = str(option.price_modifier)
            option.price_modifier = price_modifier
            option.is_available = True
            option.save(update_fields=['price_modifier', 'is_available'])

        option.items.add(item)

        return {
            'application_status': 'applied',
            'application_summary': 'Menu option created from AI recommendation.',
            'application': {
                'action': 'create_option',
                'group_id': group.id,
                'group_name': group.name,
                'option_id': option.id,
                'option_name': option.name,
                'group_created': group_created,
                'option_created': option_created,
                'previous_item_assignment': previous_item_assignment,
                'previous_option_is_available': previous_option_is_available,
                'previous_price_modifier': previous_price_modifier,
            },
        }

    def _apply_existing_option_recommendation(self, recommendation):
        """Apply an AI recommendation on an existing category option."""
        item = recommendation.item
        payload = recommendation.payload or {}
        option_id = payload.get('existing_option_id')
        suggested_action = (payload.get('suggested_action') or 'keep').strip().lower()

        option = Option.objects.filter(id=option_id, group__category=item.category).first()
        if option is None:
            return {
                'application_status': 'manual_review_required',
                'application_summary': 'Existing option no longer exists. Manual review required.',
            }

        previous_item_assignment = option.items.filter(pk=item.pk).exists()
        previous_option_is_available = option.is_available
        action = 'link_existing_option'
        summary = 'Existing option linked to this item.'

        if suggested_action == 'disable':
            option.items.remove(item)
            action = 'unlink_existing_option'
            summary = 'Existing option removed from this item.'
        elif suggested_action == 'enable':
            option.items.add(item)
            if not option.is_available:
                option.is_available = True
                option.save(update_fields=['is_available'])
            summary = 'Existing option enabled for this item.'
        else:
            summary = 'Existing option reviewed. No menu change was necessary.'

        return {
            'application_status': 'applied',
            'application_summary': summary,
            'application': {
                'action': action,
                'group_id': option.group_id,
                'group_name': option.group.name,
                'option_id': option.id,
                'option_name': option.name,
                'group_created': False,
                'option_created': False,
                'previous_item_assignment': previous_item_assignment,
                'previous_option_is_available': previous_option_is_available,
                'suggested_action': suggested_action,
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