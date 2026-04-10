from django.contrib import admin
from common.admin import OwnerRestrictedAdminMixin
from .models import Menu, Category, Item, Combo, ComboItem, OptionGroup, Option


class OptionInline(admin.TabularInline):
    model = Option
    extra = 0
    fields = ('name', 'price_modifier', 'is_available')


class OptionGroupInline(admin.TabularInline):
    model = OptionGroup
    extra = 0
    fields = ('name', 'required', 'min_choices', 'max_choices')
    inlines = [OptionInline]


class ItemInline(admin.TabularInline):
    model = Item
    extra = 0
    fields = ('name', 'base_price', 'is_available', 'display_order')
    autocomplete_fields = ('compatible_preferences',)


class ComboItemInline(admin.TabularInline):
    model = ComboItem
    extra = 0
    fields = ('display_name', 'item', 'quantity', 'display_order')


@admin.register(Combo)
class ComboAdmin(OwnerRestrictedAdminMixin, admin.ModelAdmin):
    list_display = ('name', 'category', 'combo_price', 'is_available')
    search_fields = ('name', 'category__name', 'category__menu__food_truck__name')
    list_filter = ('is_available', 'category__menu')
    inlines = [ComboItemInline]

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related('category__menu__food_truck').prefetch_related('combo_items__item')

    def _filter_by_food_trucks(self, qs, truck_ids):
        return qs.filter(category__menu__food_truck_id__in=truck_ids)

    def _object_belongs_to_trucks(self, obj, truck_ids):
        return obj.category.menu.food_truck_id in truck_ids


@admin.register(ComboItem)
class ComboItemAdmin(OwnerRestrictedAdminMixin, admin.ModelAdmin):
    list_display = ('display_name', 'combo', 'item', 'quantity')
    search_fields = ('display_name', 'combo__name', 'combo__category__menu__food_truck__name', 'item__name')
    list_filter = ('combo__category__menu',)

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related('combo__category__menu__food_truck', 'item')

    def _filter_by_food_trucks(self, qs, truck_ids):
        return qs.filter(combo__category__menu__food_truck_id__in=truck_ids)

    def _object_belongs_to_trucks(self, obj, truck_ids):
        return obj.combo.category.menu.food_truck_id in truck_ids


class CategoryInline(admin.TabularInline):
    model = Category
    extra = 0
    fields = ('name', 'display_order')
    inlines = [ItemInline]


@admin.register(Menu)
class MenuAdmin(OwnerRestrictedAdminMixin, admin.ModelAdmin):
    list_display = ('name', 'food_truck', 'is_active')
    search_fields = ('name', 'food_truck__name')
    list_filter = ('is_active',)
    inlines = [CategoryInline]

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related('food_truck')

    def _filter_by_food_trucks(self, qs, truck_ids):
        """Filter menus by food truck ownership."""
        return qs.filter(food_truck_id__in=truck_ids)

    def _object_belongs_to_trucks(self, obj, truck_ids):
        """Check if menu's food truck belongs to user."""
        return obj.food_truck_id in truck_ids


@admin.register(Category)
class CategoryAdmin(OwnerRestrictedAdminMixin, admin.ModelAdmin):
    list_display = ('name', 'menu', 'display_order')
    search_fields = ('name', 'menu__name', 'menu__food_truck__name')
    list_filter = ('menu',)
    inlines = [ItemInline]

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related('menu__food_truck')

    def _filter_by_food_trucks(self, qs, truck_ids):
        """Filter categories by food truck ownership."""
        return qs.filter(menu__food_truck_id__in=truck_ids)

    def _object_belongs_to_trucks(self, obj, truck_ids):
        """Check if category's menu's food truck belongs to user."""
        return obj.menu.food_truck_id in truck_ids


@admin.register(Item)
class ItemAdmin(OwnerRestrictedAdminMixin, admin.ModelAdmin):
    list_display = ('name', 'category', 'base_price', 'is_available')
    search_fields = ('name', 'category__name', 'category__menu__name', 'category__menu__food_truck__name')
    list_filter = ('is_available', 'category__menu')
    autocomplete_fields = ('compatible_preferences',)
    inlines = [OptionGroupInline]

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related('category__menu__food_truck').prefetch_related('compatible_preferences')

    def _filter_by_food_trucks(self, qs, truck_ids):
        """Filter items by food truck ownership."""
        return qs.filter(category__menu__food_truck_id__in=truck_ids)

    def _object_belongs_to_trucks(self, obj, truck_ids):
        """Check if item's category's menu's food truck belongs to user."""
        return obj.category.menu.food_truck_id in truck_ids


@admin.register(OptionGroup)
class OptionGroupAdmin(OwnerRestrictedAdminMixin, admin.ModelAdmin):
    list_display = ('name', 'item', 'required', 'min_choices', 'max_choices')
    search_fields = ('name', 'item__name', 'item__category__name', 'item__category__menu__food_truck__name')
    list_filter = ('required', 'item__category__menu')
    inlines = [OptionInline]

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related('item__category__menu__food_truck')

    def _filter_by_food_trucks(self, qs, truck_ids):
        """Filter option groups by food truck ownership."""
        return qs.filter(item__category__menu__food_truck_id__in=truck_ids)

    def _object_belongs_to_trucks(self, obj, truck_ids):
        """Check if option group's item's category's menu's food truck belongs to user."""
        return obj.item.category.menu.food_truck_id in truck_ids


@admin.register(Option)
class OptionAdmin(OwnerRestrictedAdminMixin, admin.ModelAdmin):
    list_display = ('name', 'group', 'price_modifier', 'is_available')
    search_fields = ('name', 'group__name', 'group__item__name', 'group__item__category__menu__food_truck__name')
    list_filter = ('is_available', 'group__item__category__menu')

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related('group__item__category__menu__food_truck')

    def _filter_by_food_trucks(self, qs, truck_ids):
        """Filter options by food truck ownership."""
        return qs.filter(group__item__category__menu__food_truck_id__in=truck_ids)

    def _object_belongs_to_trucks(self, obj, truck_ids):
        """Check if option's group's item's category's menu's food truck belongs to user."""
        return obj.group.item.category.menu.food_truck_id in truck_ids
