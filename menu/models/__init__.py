from decimal import Decimal
from django.core.exceptions import ValidationError
from django.db import models
from django.conf import settings
from django.utils.translation import gettext_lazy as _


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

    def get_price_with_options(self, selected_options):
        """
        Calculate the total price including selected options.

        Args:
            selected_options: List of Option IDs

        Returns:
            Decimal: Total price

        Raises:
            ValidationError: If options are invalid
        """
        self.validate_options(selected_options)

        total_price = self.base_price

        if selected_options:
            options = Option.objects.filter(id__in=selected_options)
            for option in options:
                total_price += option.price_modifier

        return total_price

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

        # Get all option groups for this item
        groups = self.option_groups.all()

        # Group selected options by their groups
        selected_by_group = {}
        for option_id in selected_options:
            try:
                option = Option.objects.get(id=option_id, group__item=self)
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


class OptionGroup(models.Model):
    """
    Represents a group of options for item customization (e.g., Size, Extras).
    """
    item = models.ForeignKey(
        Item,
        on_delete=models.CASCADE,
        related_name='option_groups',
        help_text=_("The item this option group belongs to")
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
        return f"{self.item.name} - {self.name}"

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
