from django import forms
from django.forms import BaseInlineFormSet, inlineformset_factory

from menu.models import Combo, ComboItem, Item


class ComboOwnerForm(forms.ModelForm):
    class Meta:
        model = Combo
        fields = ['name', 'description', 'combo_price', 'is_available', 'display_order']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
            'combo_price': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0'}),
            'is_available': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'display_order': forms.NumberInput(attrs={'class': 'form-control', 'min': '0'}),
        }


class ComboItemForm(forms.ModelForm):
    class Meta:
        model = ComboItem
        fields = ['display_name', 'item', 'quantity', 'display_order']
        widgets = {
            'display_name': forms.TextInput(attrs={'class': 'form-control'}),
            'item': forms.Select(attrs={'class': 'form-select'}),
            'quantity': forms.NumberInput(attrs={'class': 'form-control text-center', 'min': '1', 'step': '1'}),
            'display_order': forms.NumberInput(attrs={'class': 'form-control text-center', 'min': '0', 'step': '1'}),
        }

    def __init__(self, *args, available_items=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['item'].queryset = available_items or Item.objects.none()
        self.fields['display_name'].label = 'Display name'
        self.fields['display_order'].label = 'Display order'


class BaseComboItemFormSet(BaseInlineFormSet):
    def __init__(self, *args, available_items=None, **kwargs):
        self.available_items = available_items
        super().__init__(*args, **kwargs)

    def _construct_form(self, i, **kwargs):
        kwargs['available_items'] = self.available_items
        return super()._construct_form(i, **kwargs)


ComboItemFormSet = inlineformset_factory(
    Combo,
    ComboItem,
    form=ComboItemForm,
    formset=BaseComboItemFormSet,
    extra=1,
    can_delete=True,
)