from decimal import Decimal
from django.core.exceptions import ValidationError
from foodtrucks.models import FoodTruck
from menu.models import Combo, Item, Option


class CartService:
    """Session-backed cart service for MVP ordering."""

    SESSION_KEY = 'cart'

    def __init__(self, session):
        self.session = session
        self.cart = session.get(self.SESSION_KEY, {
            'foodtruck_slug': None,
            'items': [],
        })

    def _save(self):
        self.session[self.SESSION_KEY] = self.cart
        self.session.modified = True

    @staticmethod
    def _line_key(line_type, object_id, selected_options=None):
        selected_options = selected_options or []
        normalized_options = sorted(str(option_id) for option_id in selected_options)
        return f"{line_type}:{object_id}:{','.join(normalized_options)}"

    def get_cart(self):
        option_map = self._build_option_map()
        foodtruck = self._get_foodtruck()
        item_map, combo_map = self._build_product_maps()
        items = []

        for item in self.cart.get('items', []):
            selected_options = [
                {
                    'option_id': option_id,
                    'name': option_map.get(option_id).name if option_map.get(option_id) else None,
                    'price_modifier': str(option_map.get(option_id).price_modifier) if option_map.get(option_id) else None,
                }
                for option_id in item.get('selected_options', [])
            ]

            combo_components = []
            for component in item.get('combo_components', []):
                combo_components.append({
                    **component,
                    'selected_options': [
                        {
                            'option_id': option.get('option_id'),
                            'name': option_map.get(option.get('option_id')).name if option_map.get(option.get('option_id')) else option.get('name'),
                            'price_modifier': str(option_map.get(option.get('option_id')).price_modifier) if option_map.get(option.get('option_id')) else option.get('price_modifier'),
                        }
                        for option in component.get('selected_options', [])
                    ],
                })

            display_unit_price = item.get('unit_price')
            display_total_price = item.get('total_price')
            if foodtruck is not None:
                if item.get('line_type') == 'combo' and item.get('combo_id') in combo_map:
                    combo = combo_map[item.get('combo_id')]
                    display_unit_price = str(foodtruck.get_display_price(Decimal(item.get('unit_price', '0.00')), combo.get_tax_rate()))
                    display_total_price = str(foodtruck.get_display_price(Decimal(item.get('total_price', '0.00')), combo.get_tax_rate()))
                elif item.get('item_id') in item_map:
                    menu_item = item_map[item.get('item_id')]
                    display_unit_price = str(foodtruck.get_display_price(Decimal(item.get('unit_price', '0.00')), menu_item.get_tax_rate()))
                    display_total_price = str(foodtruck.get_display_price(Decimal(item.get('total_price', '0.00')), menu_item.get_tax_rate()))

            items.append({
                'line_type': item.get('line_type', 'item'),
                'item_id': item.get('item_id'),
                'combo_id': item.get('combo_id'),
                **item,
                'selected_options': selected_options,
                'combo_components': combo_components,
                'display_unit_price': display_unit_price,
                'display_total_price': display_total_price,
            })

        return {
            'foodtruck_slug': self.cart.get('foodtruck_slug'),
            'items': items,
            'total_price': str(self.get_total()),
            'display_total_price': str(sum(Decimal(item['display_total_price']) for item in items)) if items else '0.00',
            'item_count': sum(item['quantity'] for item in self.cart.get('items', [])),
            'prices_include_tax': foodtruck.prices_include_tax() if foodtruck is not None else False,
        }

    def _get_foodtruck(self):
        slug = self.cart.get('foodtruck_slug')
        if not slug:
            return None
        return FoodTruck.objects.filter(slug=slug).first()

    def _build_product_maps(self):
        item_ids = {item.get('item_id') for item in self.cart.get('items', []) if item.get('item_id')}
        combo_ids = {item.get('combo_id') for item in self.cart.get('items', []) if item.get('combo_id')}
        item_map = {item.id: item for item in Item.objects.select_related('tax', 'category__menu__food_truck').filter(id__in=item_ids)}
        combo_map = {combo.id: combo for combo in Combo.objects.select_related('tax', 'category__menu__food_truck').filter(id__in=combo_ids)}
        return item_map, combo_map

    def _build_option_map(self):
        option_ids = set(
            option_id
            for item in self.cart.get('items', [])
            for option_id in item.get('selected_options', [])
        )
        option_ids.update(
            option.get('option_id')
            for item in self.cart.get('items', [])
            for component in item.get('combo_components', [])
            for option in component.get('selected_options', [])
            if option.get('option_id') is not None
        )
        if not option_ids:
            return {}
        return {option.id: option for option in Option.objects.filter(id__in=option_ids)}

    def get_total(self):
        return sum(
            Decimal(item['total_price']) for item in self.cart.get('items', [])
        ) if self.cart.get('items') else Decimal('0.00')

    def clear(self):
        self.cart = {'foodtruck_slug': None, 'items': []}
        self._save()

    def add_item(self, foodtruck_slug, item_id, quantity=1, selected_options=None):
        selected_options = selected_options or []

        if quantity <= 0:
            raise ValidationError('Quantity must be greater than zero.')

        item = Item.objects.select_related('category__menu__food_truck').prefetch_related(
            'available_options__group',
        ).get(id=item_id)

        if not item.is_available_now():
            raise ValidationError(f"Item '{item.name}' is not available.")

        if item.category.menu.food_truck.slug != foodtruck_slug:
            raise ValidationError('Item does not belong to the requested foodtruck.')

        if self.cart['foodtruck_slug'] and self.cart['foodtruck_slug'] != foodtruck_slug:
            raise ValidationError('Cart cannot mix items from different foodtrucks.')

        item.validate_options(selected_options)
        unit_price = item.get_price_with_options(selected_options)
        line_key = self._line_key('item', item_id, selected_options)

        existing_item = next((line for line in self.cart['items'] if line['line_key'] == line_key), None)
        if existing_item:
            existing_item['quantity'] += quantity
            existing_item['total_price'] = str(Decimal(existing_item['unit_price']) * existing_item['quantity'])
        else:
            self.cart['items'].append({
                'line_key': line_key,
                'line_type': 'item',
                'item_id': item.id,
                'combo_id': None,
                'item_name': item.name,
                'quantity': quantity,
                'unit_price': str(unit_price),
                'total_price': str(unit_price * quantity),
                'selected_options': [int(option_id) for option_id in selected_options],
            })

        self.cart['foodtruck_slug'] = foodtruck_slug
        self._save()

    def add_combo(self, foodtruck_slug, combo_id, quantity=1, combo_selections=None):
        if quantity <= 0:
            raise ValidationError('Quantity must be greater than zero.')

        combo = Combo.objects.select_related('category__menu__food_truck').prefetch_related('combo_items').get(id=combo_id)

        if not combo.is_available:
            raise ValidationError(f"Combo '{combo.name}' is not available.")

        if combo.category.menu.food_truck.slug != foodtruck_slug:
            raise ValidationError('Combo does not belong to the requested foodtruck.')

        if self.cart['foodtruck_slug'] and self.cart['foodtruck_slug'] != foodtruck_slug:
            raise ValidationError('Cart cannot mix items from different foodtrucks.')

        snapshot = combo.build_order_snapshot(combo_selections=combo_selections)
        unit_price = snapshot['unit_price']

        serialized_selection = []
        for component in snapshot['components']:
            option_ids = sorted(int(option['option_id']) for option in component.get('selected_options', []))
            serialized_selection.append(f"{component['combo_item_id']}:{component['item_id']}:{'-'.join(str(option_id) for option_id in option_ids)}")
        line_key = self._line_key('combo', combo_id, serialized_selection)
        existing_item = next((line for line in self.cart['items'] if line['line_key'] == line_key), None)
        if existing_item:
            existing_item['quantity'] += quantity
            existing_item['total_price'] = str(Decimal(existing_item['unit_price']) * existing_item['quantity'])
        else:
            self.cart['items'].append({
                'line_key': line_key,
                'line_type': 'combo',
                'item_id': None,
                'combo_id': combo.id,
                'item_name': combo.name,
                'component_summary': snapshot['component_summary'],
                'combo_components': snapshot['components'],
                'quantity': quantity,
                'unit_price': str(unit_price),
                'total_price': str(unit_price * quantity),
                'selected_options': [],
            })

        self.cart['foodtruck_slug'] = foodtruck_slug
        self._save()

    def remove_item(self, line_key):
        existing_items = [item for item in self.cart.get('items', []) if item['line_key'] != line_key]
        if len(existing_items) == len(self.cart.get('items', [])):
            raise ValidationError('Cart item not found.')

        self.cart['items'] = existing_items
        if not self.cart['items']:
            self.cart['foodtruck_slug'] = None
        self._save()

    def update_item_quantity(self, line_key, quantity):
        if quantity <= 0:
            raise ValidationError('Quantity must be greater than zero.')

        existing_item = next((item for item in self.cart.get('items', []) if item['line_key'] == line_key), None)
        if existing_item is None:
            raise ValidationError('Cart item not found.')

        existing_item['quantity'] = quantity
        existing_item['total_price'] = str(Decimal(existing_item['unit_price']) * quantity)
        self._save()
