from django import forms
from django.utils.translation import gettext_lazy as _

from .models import Location, ServiceSchedule
from .services.location_geocoding_service import LocationGeocodingService


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
        help_texts = {
            'address_line_1': _('If you provide an address only, GPS coordinates will be resolved automatically.'),
            'latitude': _('If you provide GPS coordinates only, the address fields will be resolved automatically.'),
            'longitude': _('If you provide GPS coordinates only, the address fields will be resolved automatically.'),
        }

    def __init__(self, *args, food_truck=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.food_truck = food_truck
        for field_name in ['address_line_1', 'address_line_2', 'postal_code', 'city', 'country', 'latitude', 'longitude']:
            self.fields[field_name].required = False

        for name, field in self.fields.items():
            if isinstance(field.widget, forms.CheckboxInput):
                existing_class = field.widget.attrs.get('class', '')
                field.widget.attrs['class'] = f'{existing_class} form-check-input'.strip()
                continue

            existing_class = field.widget.attrs.get('class', '')
            field.widget.attrs['class'] = f'{existing_class} form-control'.strip()

        self.fields['notes'].widget.attrs['rows'] = 4
        self.fields['name'].widget.attrs['placeholder'] = _('e.g. Lunch spot République')
        self.fields['address_line_1'].widget.attrs['placeholder'] = _('Street and number')
        self.fields['address_line_2'].widget.attrs['placeholder'] = _('Building, floor, landmark')
        self.fields['postal_code'].widget.attrs['placeholder'] = _('Postal code')
        self.fields['city'].widget.attrs['placeholder'] = _('City')
        self.fields['country'].widget.attrs['placeholder'] = _('Country')
        self.fields['latitude'].widget.attrs['placeholder'] = '48.856600'
        self.fields['longitude'].widget.attrs['placeholder'] = '2.352200'

    def clean(self):
        cleaned = super().clean()
        has_address = cleaned.get('address_line_1')
        has_coords = cleaned.get('latitude') is not None and cleaned.get('longitude') is not None
        if not has_address and not has_coords:
            raise forms.ValidationError(
                _('Provide either an address or GPS coordinates to define the location.')
            )

        location = self.instance if self.instance.pk else Location(food_truck=self.food_truck)
        for field_name in self.Meta.fields:
            if field_name in cleaned:
                setattr(location, field_name, cleaned.get(field_name))

        try:
            location.resolve_geodata(geocoding_service=LocationGeocodingService)
        except forms.ValidationError:
            raise
        except Exception as exc:
            raise forms.ValidationError(str(exc))

        cleaned['address_line_1'] = location.address_line_1
        cleaned['address_line_2'] = location.address_line_2
        cleaned['postal_code'] = location.postal_code
        cleaned['city'] = location.city
        cleaned['country'] = location.country
        cleaned['latitude'] = location.latitude
        cleaned['longitude'] = location.longitude
        return cleaned
