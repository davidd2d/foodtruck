from decimal import Decimal
from django.core.exceptions import ValidationError
from django.db import models
from django.conf import settings
from django.utils.translation import gettext_lazy as _

from common.models import Tax


class Menu(models.Model):
    """
    Represents a menu for a food truck.

    A menu contains categories and items, and can be active or inactive.
    """
    food_truck = models.ForeignKey(
        'foodtrucks.FoodTruck',
        on_delete=models.CASCADE,
        related_name='menus',
        help_text=_("The food truck this menu belongs to")
    )
    name = models.CharField(max_length=200, help_text=_("Name of the menu"))
    is_active = models.BooleanField(default=True, help_text=_("Whether the menu is active"))
    created_at = models.DateTimeField(auto_now_add=True, help_text=_("When the menu was created"))

    class Meta:
        verbose_name = _("Menu")
        verbose_name_plural = _("Menus")
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.food_truck.name} - {self.name}"


class Category(models.Model):
    """
    Represents a category within a menu (e.g., Appetizers, Main Courses).
    """
    menu = models.ForeignKey(
        Menu,
        on_delete=models.CASCADE,
        related_name='categories',
        help_text=_("The menu this category belongs to")
    )
    name = models.CharField(max_length=200, help_text=_("Name of the category"))
    display_order = models.PositiveIntegerField(default=0, help_text=_("Order for display"))

    class Meta:
        verbose_name = _("Category")
        verbose_name_plural = _("Categories")
        ordering = ['display_order', 'name']
        indexes = [
            models.Index(fields=['menu']),
        ]

    def __str__(self):
        return self.name


class Item(models.Model):
    """
    Represents a menu item with pricing and customization options.
    """
    category = models.ForeignKey(
        Category,
        on_delete=models.CASCADE,
        related_name='items',
        help_text=_("The category this item belongs to")
    )
    name = models.CharField(max_length=200, help_text=_("Name of the item"))
    description = models.TextField(blank=True, help_text=_("Description of the item"))
    tax = models.ForeignKey(
        'common.Tax',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='items',
        help_text=_("Tax configuration applied to this item")
    )
    base_price = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        help_text=_("Base price of the item")
    )
    is_available = models.BooleanField(default=True, help_text=_("Whether the item is available"))
    display_order = models.PositiveIntegerField(default=0, help_text=_("Order for display"))

    # Preferences
    compatible_preferences = models.ManyToManyField(
        'preferences.Preference',
        blank=True,
        help_text=_("Dietary preferences this item is compatible with")
    )

    class Meta:
        verbose_name = _("Item")
        verbose_name_plural = _("Items")
        ordering = ['display_order', 'name']
        indexes = [
            models.Index(fields=['is_available']),
            models.Index(fields=['category']),
        ]

    def __str__(self):
        return self.name

    def get_option_groups_queryset(self):
        """Return option groups available to this item in its category."""
        return OptionGroup.objects.filter(
            category=self.category,
            options__items=self,
        ).distinct()

    def get_tax_rate(self):
        if self.tax_id and self.tax.is_active:
            return self.tax.rate

        foodtruck = getattr(getattr(self.category, 'menu', None), 'food_truck', None)
        country = None
        if foodtruck is not None:
            country = getattr(foodtruck, 'country', None) or getattr(foodtruck, 'billing_country', None)

        default_tax = Tax.objects.default(country=country)
        if default_tax is None:
            raise ValidationError('No default tax configured.')
        return default_tax.rate

    def get_price_with_options(self, selected_options=None):
        """
        Calculate the total price including selected options.

        Args:
            selected_options: List of Option IDs

        Returns:
            Decimal: Total price

        Raises:
            ValidationError: If options are invalid
        """
        selected_options = selected_options or []
        self.validate_options(selected_options)

        total_price = self.base_price

        if selected_options:
            options = Option.objects.filter(id__in=selected_options)
            for option in options:
                total_price += option.price_modifier

        return total_price

    def is_available_now(self):
        """Return whether the item is available for purchase now."""
        return bool(self.is_available)

    def is_compatible_with(self, preferences):
        """
        Check if the item is compatible with all given preferences.

        Args:
            preferences: List of Preference instances or IDs

        Returns:
            bool: True if compatible with all preferences
        """
        if not preferences:
            return True

        compatible_ids = set(self.compatible_preferences.values_list('id', flat=True))
        required_ids = set(p.id if hasattr(p, 'id') else p for p in preferences)

        return required_ids.issubset(compatible_ids)

    def validate_options(self, selected_options):
        """
        Validate selected options against item constraints.

        Args:
            selected_options: List of Option IDs

        Raises:
            ValidationError: If validation fails
        """
        if not selected_options:
            selected_options = []

        # Get all option groups available for this item (direct + shared)
        groups = self.get_option_groups_queryset()

        # Group selected options by their groups
        selected_by_group = {}
        for option_id in selected_options:
            try:
                option = Option.objects.get(
                    id=option_id,
                    items=self,
                    group__category=self.category,
                )
                group_id = option.group_id
                if group_id not in selected_by_group:
                    selected_by_group[group_id] = []
                selected_by_group[group_id].append(option)
            except Option.DoesNotExist:
                raise ValidationError(f"Invalid option ID: {option_id}")

        # Validate each group
        for group in groups:
            selected_count = len(selected_by_group.get(group.id, []))

            if group.required and selected_count == 0:
                raise ValidationError(f"Required option group '{group.name}' not selected")

            if selected_count < group.min_choices:
                raise ValidationError(
                    f"Option group '{group.name}' requires at least {group.min_choices} choices, "
                    f"got {selected_count}"
                )

            if group.max_choices and selected_count > group.max_choices:
                raise ValidationError(
                    f"Option group '{group.name}' allows at most {group.max_choices} choices, "
                    f"got {selected_count}"
                )


class Combo(models.Model):
    """
    Represents a purchasable or displayable combo within a menu category.

    Combos group several menu items into a curated offer. They are modeled
    separately from regular items so their composition can evolve without
    overloading the existing item/options domain.
    """
    category = models.ForeignKey(
        Category,
        on_delete=models.CASCADE,
        related_name='combos',
        help_text=_("The category this combo belongs to")
    )
    name = models.CharField(max_length=200, help_text=_("Name of the combo"))
    description = models.TextField(blank=True, help_text=_("Description of the combo"))
    tax = models.ForeignKey(
        'common.Tax',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='combos',
        help_text=_("Tax configuration applied to this combo")
    )
    combo_price = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        null=True,
        blank=True,
        help_text=_("Explicit combo price when known")
    )
    discount_amount = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text=_("Owner-defined reduction applied to the composed combo")
    )
    is_available = models.BooleanField(default=True, help_text=_("Whether the combo is available"))
    display_order = models.PositiveIntegerField(default=0, help_text=_("Order for display"))

    class Meta:
        verbose_name = _("Combo")
        verbose_name_plural = _("Combos")
        ordering = ['display_order', 'name']
        indexes = [
            models.Index(fields=['category']),
            models.Index(fields=['is_available']),
        ]

    def __str__(self):
        return self.name

    def get_effective_price(self):
        """Return the explicit combo price, or infer one from resolved component items."""
        if self.combo_price is not None:
            return self.combo_price

        combo_items = list(
            self.combo_items.select_related('item', 'source_category').prefetch_related('fixed_items')
        )
        if not combo_items:
            return None

        total = Decimal('0.00')
        for combo_item in combo_items:
            if combo_item.source_category_id:
                return None

            fixed_items = combo_item.get_fixed_items()
            if not fixed_items:
                return None

            total += sum(fixed_item.base_price for fixed_item in fixed_items) * combo_item.quantity

        return max(Decimal('0.00'), total - (self.discount_amount or Decimal('0.00')))

    @property
    def is_customizable(self):
        return self.combo_items.filter(source_category__isnull=False).exists()

    @staticmethod
    def _normalize_selected_options(selected_options_payload):
        selected_options = []
        for option_entry in selected_options_payload or []:
            if isinstance(option_entry, dict):
                option_id = option_entry.get('option_id')
            else:
                option_id = option_entry
            if option_id is None:
                continue
            selected_options.append(int(option_id))
        return selected_options

    def _append_component_snapshot(self, components, combo_item, chosen_item, selected_options):
        option_objects = Option.objects.filter(
            id__in=selected_options,
            items=chosen_item,
            group__category=chosen_item.category,
            is_available=True,
        )
        option_map = {option.id: option for option in option_objects}
        foodtruck = getattr(getattr(getattr(chosen_item, 'category', None), 'menu', None), 'food_truck', None)
        item_tax_rate = chosen_item.get_tax_rate()

        components.append({
            'combo_item_id': combo_item.id,
            'label': combo_item.display_name,
            'item_id': chosen_item.id,
            'item_name': chosen_item.name,
            'quantity': combo_item.quantity,
            'source_category_id': combo_item.source_category_id,
            'source_category_name': combo_item.source_category.name if combo_item.source_category_id else '',
            'selected_options': [
                {
                    'option_id': option_id,
                    'name': option_map[option_id].name,
                    'price_modifier': str(option_map[option_id].price_modifier),
                    'display_price_modifier': str(
                        foodtruck.get_display_price(option_map[option_id].price_modifier, item_tax_rate)
                    ) if foodtruck is not None else str(option_map[option_id].price_modifier),
                }
                for option_id in selected_options
                if option_id in option_map
            ],
        })

    def build_order_snapshot(self, combo_selections=None):
        combo_selections = combo_selections or []
        selection_map = {}
        for selection in combo_selections:
            combo_item_id = selection.get('combo_item_id')
            if not combo_item_id:
                continue
            selection_map.setdefault(int(combo_item_id), []).append(selection)

        combo_items = list(
            self.combo_items.select_related('item__category', 'source_category')
            .prefetch_related(
                'fixed_items',
                'fixed_items__available_options__group',
            )
            .order_by('display_order', 'id')
        )
        if not combo_items:
            raise ValidationError(f"Combo '{self.name}' has no composition.")

        subtotal = Decimal('0.00')
        components = []

        for combo_item in combo_items:
            selected_payloads = selection_map.get(combo_item.id, [])

            if combo_item.source_category_id:
                selected_payload = selected_payloads[0] if selected_payloads else {}
                chosen_item = combo_item.resolve_selected_item(selected_payload.get('item_id'))
                selected_options = self._normalize_selected_options(selected_payload.get('selected_options', []))

                chosen_item.validate_options(selected_options)
                component_unit_price = chosen_item.get_price_with_options(selected_options)
                subtotal += component_unit_price * combo_item.quantity
                self._append_component_snapshot(components, combo_item, chosen_item, selected_options)
                continue

            fixed_items = combo_item.get_fixed_items()
            if not fixed_items:
                raise ValidationError(f"{combo_item.display_name} requires at least one fixed item.")

            payload_by_item_id = {
                int(payload['item_id']): payload
                for payload in selected_payloads
                if payload.get('item_id')
            }

            for fixed_item in fixed_items:
                if not fixed_item.is_available_now():
                    raise ValidationError(f"Item '{fixed_item.name}' is not available.")

                selected_payload = payload_by_item_id.get(fixed_item.id, {})
                selected_options = self._normalize_selected_options(selected_payload.get('selected_options', []))

                fixed_item.validate_options(selected_options)
                component_unit_price = fixed_item.get_price_with_options(selected_options)
                subtotal += component_unit_price * combo_item.quantity
                self._append_component_snapshot(components, combo_item, fixed_item, selected_options)

        unit_price = self.combo_price if self.combo_price is not None else max(
            Decimal('0.00'),
            subtotal - (self.discount_amount or Decimal('0.00')),
        )

        def _format_component(component):
            base = f"{component['quantity']}x {component['item_name']}" if component['quantity'] > 1 else component['item_name']
            options = component.get('selected_options', [])
            if options:
                option_names = ', '.join(opt['name'] for opt in options)
                return f"{base} ({option_names})"
            return base

        component_summary = ', '.join(_format_component(c) for c in components)

        options_extra = sum(
            Decimal(opt['price_modifier']) * component['quantity']
            for component in components
            for opt in component.get('selected_options', [])
        )
        if self.combo_price is not None:
            unit_price = self.combo_price + options_extra

        return {
            'unit_price': unit_price,
            'subtotal': subtotal,
            'discount_amount': self.discount_amount or Decimal('0.00'),
            'component_summary': component_summary,
            'components': components,
        }

    def get_tax_rate(self):
        if self.tax_id and self.tax.is_active:
            return self.tax.rate

        foodtruck = getattr(getattr(self.category, 'menu', None), 'food_truck', None)
        country = None
        if foodtruck is not None:
            country = getattr(foodtruck, 'country', None) or getattr(foodtruck, 'billing_country', None)

        default_tax = Tax.objects.default(country=country)
        if default_tax is None:
            raise ValidationError('No default tax configured.')
        return default_tax.rate


class ComboItem(models.Model):
    """
    Represents one component inside a combo.

    `display_name` preserves the intended component label even when no exact
    `menu.Item` match is available in the current menu.
    """
    combo = models.ForeignKey(
        Combo,
        on_delete=models.CASCADE,
        related_name='combo_items',
        help_text=_("The combo this component belongs to")
    )
    item = models.ForeignKey(
        Item,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='combo_memberships',
        help_text=_("Legacy fixed item for this combo component")
    )
    fixed_items = models.ManyToManyField(
        Item,
        blank=True,
        related_name='fixed_combo_components',
        help_text=_("Fixed menu items always included for this combo component")
    )
    source_category = models.ForeignKey(
        Category,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='combo_components',
        help_text=_("Category from which the customer chooses the item for this combo component")
    )
    display_name = models.CharField(max_length=200, help_text=_("Display name of the combo component"))
    quantity = models.PositiveIntegerField(default=1, help_text=_("Quantity of this component in the combo"))
    display_order = models.PositiveIntegerField(default=0, help_text=_("Order for display"))

    class Meta:
        verbose_name = _("Combo Item")
        verbose_name_plural = _("Combo Items")
        ordering = ['display_order', 'id']

    def __str__(self):
        return f"{self.combo.name} - {self.display_name}"

    def get_fixed_items(self):
        fixed_items = list(self.fixed_items.all())
        if fixed_items:
            return fixed_items
        if self.item_id:
            return [self.item]
        return []

    def clean(self):
        has_fixed_items = bool(self.item_id)
        if self.pk:
            has_fixed_items = has_fixed_items or self.fixed_items.exists()

        if not has_fixed_items and not self.source_category_id:
            raise ValidationError("A combo component needs either fixed item(s) or a source category.")

        if self.item_id and self.source_category_id and self.item.category_id != self.source_category_id:
            raise ValidationError("The fixed item must belong to the selected source category.")

        if self.pk and self.source_category_id and self.fixed_items.exclude(category_id=self.source_category_id).exists():
            raise ValidationError("All fixed items must belong to the selected source category.")

    def resolve_selected_item(self, selected_item_id=None):
        if not self.source_category_id:
            fixed_items = self.get_fixed_items()
            if not fixed_items:
                raise ValidationError(f"{self.display_name} has no fixed item configured.")

            if selected_item_id:
                fixed_ids = {fixed_item.id for fixed_item in fixed_items}
                if int(selected_item_id) not in fixed_ids:
                    raise ValidationError(f"{self.display_name} is fixed and cannot be replaced.")
                chosen_item = next(fixed_item for fixed_item in fixed_items if fixed_item.id == int(selected_item_id))
            else:
                chosen_item = fixed_items[0]

            if not chosen_item.is_available_now():
                raise ValidationError(f"Item '{chosen_item.name}' is not available.")
            return chosen_item

        if not selected_item_id:
            raise ValidationError(f"Choose an item for '{self.display_name}'.")

        try:
            selected_item = Item.objects.prefetch_related(
                'available_options__group',
            ).get(pk=selected_item_id)
        except Item.DoesNotExist as exc:
            raise ValidationError(f"Selected item for '{self.display_name}' does not exist.") from exc

        if selected_item.category_id != self.source_category_id:
            raise ValidationError(f"Selected item does not belong to '{self.display_name}'.")

        if self.combo.category.menu_id != selected_item.category.menu_id:
            raise ValidationError("Selected combo item must belong to the same menu.")

        if not selected_item.is_available_now():
            raise ValidationError(f"Item '{selected_item.name}' is not available.")

        return selected_item


class OptionGroup(models.Model):
    """
    Represents a category-level group of options (e.g., Free pizza options).
    """
    category = models.ForeignKey(
        Category,
        on_delete=models.CASCADE,
        related_name='option_groups',
        help_text=_("The category this option group belongs to")
    )
    name = models.CharField(max_length=200, help_text=_("Name of the option group"))
    required = models.BooleanField(default=False, help_text=_("Whether this group is required"))
    min_choices = models.PositiveIntegerField(default=0, help_text=_("Minimum number of choices required"))
    max_choices = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text=_("Maximum number of choices allowed (null for unlimited)")
    )

    class Meta:
        verbose_name = _("Option Group")
        verbose_name_plural = _("Option Groups")
        ordering = ['name']

    def __str__(self):
        return f"{self.category.name} - {self.name}"

    def clean(self):
        if self.max_choices is not None and self.min_choices > self.max_choices:
            raise ValidationError("min_choices cannot be greater than max_choices")


class Option(models.Model):
    """
    Represents a single option within an option group.
    """
    group = models.ForeignKey(
        OptionGroup,
        on_delete=models.CASCADE,
        related_name='options',
        help_text=_("The option group this option belongs to")
    )
    items = models.ManyToManyField(
        Item,
        related_name='available_options',
        blank=True,
        help_text=_("Items that can use this option")
    )
    name = models.CharField(max_length=200, help_text=_("Name of the option"))
    price_modifier = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text=_("Price modifier for this option (can be negative)")
    )
    is_available = models.BooleanField(default=True, help_text=_("Whether the option is available"))

    class Meta:
        verbose_name = _("Option")
        verbose_name_plural = _("Options")
        ordering = ['name']

    def __str__(self):
        return self.name

    def get_tax_rate(self):
        assigned_item = self.items.select_related('tax', 'category__menu__food_truck').first()
        if assigned_item is not None:
            return assigned_item.get_tax_rate()

        country = None
        if self.group and self.group.category and self.group.category.menu and self.group.category.menu.food_truck:
            foodtruck = self.group.category.menu.food_truck
            country = getattr(foodtruck, 'country', None) or getattr(foodtruck, 'billing_country', None)

        default_tax = Tax.objects.default(country=country)
        if default_tax is None:
            raise ValidationError('No default tax configured.')
        return default_tax.rate
