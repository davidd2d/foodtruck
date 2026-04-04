from decimal import Decimal
from django.core.exceptions import ValidationError
from menu.models import Item, Option


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
    def _line_key(item_id, selected_options):
        selected_options = selected_options or []
        sorted_options = sorted(int(option_id) for option_id in selected_options)
        return f"{item_id}:{','.join(str(option_id) for option_id in sorted_options)}"

    def get_cart(self):
        option_map = self._build_option_map()
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

            items.append({
                **item,
                'selected_options': selected_options,
            })

        return {
            'foodtruck_slug': self.cart.get('foodtruck_slug'),
            'items': items,
            'total_price': str(self.get_total()),
            'item_count': sum(item['quantity'] for item in self.cart.get('items', [])),
        }

    def _build_option_map(self):
        option_ids = set(
            option_id
            for item in self.cart.get('items', [])
            for option_id in item.get('selected_options', [])
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

        item = Item.objects.select_related('category__menu__food_truck').prefetch_related('option_groups__options').get(id=item_id)

        if not item.is_available_now():
            raise ValidationError(f"Item '{item.name}' is not available.")

        if item.category.menu.food_truck.slug != foodtruck_slug:
            raise ValidationError('Item does not belong to the requested foodtruck.')

        if self.cart['foodtruck_slug'] and self.cart['foodtruck_slug'] != foodtruck_slug:
            raise ValidationError('Cart cannot mix items from different foodtrucks.')

        item.validate_options(selected_options)
        unit_price = item.get_price_with_options(selected_options)
        line_key = self._line_key(item_id, selected_options)

        existing_item = next((line for line in self.cart['items'] if line['line_key'] == line_key), None)
        if existing_item:
            existing_item['quantity'] += quantity
            existing_item['total_price'] = str(Decimal(existing_item['unit_price']) * existing_item['quantity'])
        else:
            self.cart['items'].append({
                'line_key': line_key,
                'item_id': item.id,
                'item_name': item.name,
                'quantity': quantity,
                'unit_price': str(unit_price),
                'total_price': str(unit_price * quantity),
                'selected_options': [int(option_id) for option_id in selected_options],
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
