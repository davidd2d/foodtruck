from django import forms
from decimal import Decimal
from django.utils.translation import gettext_lazy as _

from common.models import Tax
from menu.models import Combo, Item, Option


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


class _DisplayPriceMixin:
    display_price_field_name = None

    def _init_display_price_context(self, foodtruck=None):
        self.foodtruck = foodtruck
        self.prices_include_tax = bool(foodtruck and foodtruck.prices_include_tax())

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


class TaxChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, obj):
        return f"{obj.name} ({obj.rate * 100:.2f}%)"


class MenuImportForm(forms.Form):
    raw_text = forms.CharField(
        required=False,
        label=_('Raw text'),
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 8,
            'placeholder': _('Paste an existing menu, website copy, or pricing notes here.'),
        }),
    )
    source_url = forms.URLField(
        required=False,
        label=_('Reference URL'),
        widget=forms.URLInput(attrs={
            'class': 'form-control',
            'placeholder': 'https://example.com/menu',
        }),
    )


class ItemCatalogForm(_DisplayPriceMixin, forms.ModelForm):
    tax = TaxChoiceField(
        queryset=Tax.objects.none(),
        required=False,
        empty_label=_('Default tax'),
    )

    class Meta:
        model = Item
        fields = ['base_price', 'tax', 'is_available']
        widgets = {
            'base_price': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0'}),
            'tax': forms.Select(attrs={'class': 'form-select'}),
            'is_available': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
        labels = {
            'base_price': _('Price'),
            'tax': _('Tax'),
            'is_available': _('Available'),
        }

    def __init__(self, *args, **kwargs):
        foodtruck = kwargs.pop('foodtruck', None)
        super().__init__(*args, **kwargs)
        self._init_display_price_context(foodtruck=foodtruck)
        self.fields['tax'].queryset = Tax.objects.active().order_by('country', '-is_default', 'name')

        if self.instance and self.instance.pk:
            tax_rate = _resolve_tax_rate(self.foodtruck, self.instance.tax)
            self.initial['base_price'] = self._to_display_amount(self.instance.base_price, tax_rate)

    def clean(self):
        cleaned = super().clean()
        value = cleaned.get('base_price')
        if value is None:
            return cleaned

        selected_tax = cleaned.get('tax')
        tax_rate = _resolve_tax_rate(self.foodtruck, selected_tax)
        cleaned['base_price'] = self._to_storage_amount(value, tax_rate)
        return cleaned


class ComboCatalogForm(_DisplayPriceMixin, forms.ModelForm):
    tax = TaxChoiceField(
        queryset=Tax.objects.none(),
        required=False,
        empty_label=_('Default tax'),
    )

    class Meta:
        model = Combo
        fields = ['combo_price', 'tax', 'is_available']
        widgets = {
            'combo_price': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0'}),
            'tax': forms.Select(attrs={'class': 'form-select'}),
            'is_available': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
        labels = {
            'combo_price': _('Combo price'),
            'tax': _('Tax'),
            'is_available': _('Available'),
        }

    def __init__(self, *args, **kwargs):
        foodtruck = kwargs.pop('foodtruck', None)
        super().__init__(*args, **kwargs)
        self._init_display_price_context(foodtruck=foodtruck)
        self.fields['tax'].queryset = Tax.objects.active().order_by('country', '-is_default', 'name')

        if self.instance and self.instance.pk and self.instance.combo_price is not None:
            tax_rate = _resolve_tax_rate(self.foodtruck, self.instance.tax)
            self.initial['combo_price'] = self._to_display_amount(self.instance.combo_price, tax_rate)

    def clean(self):
        cleaned = super().clean()
        value = cleaned.get('combo_price')
        if value is None:
            return cleaned

        selected_tax = cleaned.get('tax')
        tax_rate = _resolve_tax_rate(self.foodtruck, selected_tax)
        cleaned['combo_price'] = self._to_storage_amount(value, tax_rate)
        return cleaned


class OptionCatalogForm(_DisplayPriceMixin, forms.ModelForm):
    class Meta:
        model = Option
        fields = ['price_modifier', 'is_available']
        widgets = {
            'price_modifier': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'is_available': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
        labels = {
            'price_modifier': _('Price modifier'),
            'is_available': _('Available'),
        }

    def __init__(self, *args, **kwargs):
        foodtruck = kwargs.pop('foodtruck', None)
        super().__init__(*args, **kwargs)
        self._init_display_price_context(foodtruck=foodtruck)

        if self.instance and self.instance.pk:
            tax_rate = self.instance.get_tax_rate()
            self.initial['price_modifier'] = self._to_display_amount(self.instance.price_modifier, tax_rate)

    def clean(self):
        cleaned = super().clean()
        value = cleaned.get('price_modifier')
        if value is None:
            return cleaned

        tax_rate = self.instance.get_tax_rate() if self.instance and self.instance.pk else Decimal('0.0000')
        cleaned['price_modifier'] = self._to_storage_amount(value, tax_rate)
        return cleaned