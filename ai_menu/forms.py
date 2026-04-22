from django import forms
from decimal import Decimal
from django.forms import BaseInlineFormSet, inlineformset_factory
from django.utils.translation import gettext_lazy as _

from common.models import Tax
from menu.models import Category, Combo, ComboItem, Item


def _quantize_price(value):
    return Decimal(value).quantize(Decimal('0.01'))


def _resolve_tax_rate(foodtruck, explicit_tax):
    if explicit_tax is not None and explicit_tax.is_active:
        return explicit_tax.rate

    country = None
    if foodtruck is not None:
        country = getattr(foodtruck, 'country', None) or getattr(foodtruck, 'billing_country', None)

    default_tax = Tax.objects.default(country=country)
    if default_tax is not None:
        return default_tax.rate
    return Decimal('0.0000')


class ComboOwnerForm(forms.ModelForm):
    class Meta:
        model = Combo
        fields = ['name', 'description', 'tax', 'combo_price', 'discount_amount', 'is_available', 'display_order']
        labels = {
            'name': _('Name'),
            'description': _('Description'),
            'tax': _('Tax'),
            'combo_price': _('Combo price'),
            'discount_amount': _('Combo discount'),
            'is_available': _('Is available'),
            'display_order': _('Display order'),
        }
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
            'tax': forms.Select(attrs={'class': 'form-select'}),
            'combo_price': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0'}),
            'discount_amount': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0'}),
            'is_available': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'display_order': forms.NumberInput(attrs={'class': 'form-control', 'min': '0'}),
        }

    def __init__(self, *args, **kwargs):
        self.foodtruck = kwargs.pop('foodtruck', None)
        super().__init__(*args, **kwargs)
        self.fields['tax'].queryset = Tax.objects.active().order_by('country', '-is_default', 'name')
        self.fields['tax'].empty_label = _('Default tax')
        self.prices_include_tax = bool(self.foodtruck and self.foodtruck.prices_include_tax())

        if self.instance and self.instance.pk:
            tax_rate = _resolve_tax_rate(self.foodtruck, self.instance.tax)
            if self.instance.combo_price is not None:
                self.initial['combo_price'] = self._to_display_amount(self.instance.combo_price, tax_rate)
            self.initial['discount_amount'] = self._to_display_amount(self.instance.discount_amount, tax_rate)

    def _to_display_amount(self, amount, tax_rate):
        if amount is None:
            return None
        if not self.prices_include_tax:
            return _quantize_price(amount)
        return _quantize_price(amount * (Decimal('1.00') + tax_rate))

    def _to_storage_amount(self, amount, tax_rate):
        if amount is None:
            return None
        if not self.prices_include_tax:
            return _quantize_price(amount)
        divisor = Decimal('1.00') + tax_rate
        if divisor <= 0:
            return _quantize_price(amount)
        return _quantize_price(Decimal(amount) / divisor)

    def clean(self):
        cleaned = super().clean()
        selected_tax = cleaned.get('tax')
        tax_rate = _resolve_tax_rate(self.foodtruck, selected_tax)

        combo_price = cleaned.get('combo_price')
        if combo_price is not None:
            cleaned['combo_price'] = self._to_storage_amount(combo_price, tax_rate)

        discount_amount = cleaned.get('discount_amount')
        if discount_amount is not None:
            cleaned['discount_amount'] = self._to_storage_amount(discount_amount, tax_rate)

        return cleaned


class ComboCreateForm(ComboOwnerForm):
    class Meta(ComboOwnerForm.Meta):
        fields = ['category', 'name', 'description', 'tax', 'combo_price', 'discount_amount', 'is_available', 'display_order']
        labels = {
            **ComboOwnerForm.Meta.labels,
            'category': _('Category'),
        }
        widgets = {
            **ComboOwnerForm.Meta.widgets,
            'category': forms.Select(attrs={'class': 'form-select'}),
        }

    def __init__(self, *args, **kwargs):
        available_categories = kwargs.pop('available_categories', None)
        super().__init__(*args, **kwargs)
        self.fields['category'].queryset = available_categories or Category.objects.none()


class ComboItemForm(forms.ModelForm):
    class Meta:
        model = ComboItem
        fields = ['display_name', 'source_category', 'item', 'quantity', 'display_order']
        labels = {
            'display_name': _('Display name'),
            'source_category': _('Customer choice category'),
            'item': _('Fixed item'),
            'quantity': _('Quantity'),
            'display_order': _('Display order'),
        }
        widgets = {
            'display_name': forms.TextInput(attrs={'class': 'form-control'}),
            'source_category': forms.Select(attrs={'class': 'form-select'}),
            'item': forms.Select(attrs={'class': 'form-select'}),
            'quantity': forms.NumberInput(attrs={'class': 'form-control text-center', 'min': '1', 'step': '1'}),
            'display_order': forms.NumberInput(attrs={'class': 'form-control text-center', 'min': '0', 'step': '1'}),
        }

    def __init__(self, *args, available_items=None, available_categories=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['item'].queryset = available_items or Item.objects.none()
        self.fields['source_category'].queryset = available_categories or Category.objects.none()
        self.fields['source_category'].required = False
        self.fields['item'].required = False


class BaseComboItemFormSet(BaseInlineFormSet):
    def __init__(self, *args, available_items=None, available_categories=None, **kwargs):
        self.available_items = available_items
        self.available_categories = available_categories
        super().__init__(*args, **kwargs)

    def _construct_form(self, i, **kwargs):
        kwargs['available_items'] = self.available_items
        kwargs['available_categories'] = self.available_categories
        return super()._construct_form(i, **kwargs)


ComboItemFormSet = inlineformset_factory(
    Combo,
    ComboItem,
    form=ComboItemForm,
    formset=BaseComboItemFormSet,
    extra=1,
    can_delete=True,
)