from django import forms
from django.utils.translation import gettext_lazy as _

from .models import Location, ServiceSchedule


class LocationForm(forms.ModelForm):
    class Meta:
        model = Location
        fields = [
            'name',
            'address_line_1',
            'address_line_2',
            'postal_code',
            'city',
            'country',
            'latitude',
            'longitude',
            'notes',
            'is_active',
        ]
        widgets = {
            'notes': forms.Textarea(attrs={'rows': 3}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
        labels = {
            'name': _('Spot name'),
            'address_line_1': _('Address line 1'),
            'address_line_2': _('Address line 2'),
            'postal_code': _('Postal code'),
            'city': _('City'),
            'country': _('Country'),
            'latitude': _('Latitude'),
            'longitude': _('Longitude'),
            'notes': _('Notes / instructions'),
            'is_active': _('Active location'),
        }

    def __init__(self, *args, food_truck=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.food_truck = food_truck

    def clean(self):
        cleaned = super().clean()
        has_address = cleaned.get('address_line_1')
        has_coords = cleaned.get('latitude') is not None and cleaned.get('longitude') is not None
        if not has_address and not has_coords:
            raise forms.ValidationError(
                _('Provide either an address or GPS coordinates to define the location.')
            )
        return cleaned
