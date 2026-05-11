# apps/accounts/forms.py
from django import forms
from django.contrib.auth.forms import UserCreationForm, UserChangeForm, AuthenticationForm
from django.utils.translation import gettext_lazy as _
from .models import User
from foodtrucks.models import FoodTruck
from orders.services.location_geocoding_service import LocationGeocodingService

class CustomAuthenticationForm(AuthenticationForm):
    def confirm_login_allowed(self, user):
        if not user.email_verified:
            raise forms.ValidationError(
                _("Vous devez confirmer votre adresse e-mail pour vous connecter."),
                code='email_not_verified',
            )
        if not user.is_active:
            raise forms.ValidationError(
                _("Ce compte est inactif."),
                code='inactive',
            )

    def clean_username(self):
        username = self.cleaned_data.get('username')
        return username.strip().lower() if username else username


class CustomUserCreationForm(UserCreationForm):
    email = forms.EmailField(label=_("Adresse e-mail"), help_text="")

    class Meta:
        model = User
        fields = ("email", "first_name", "last_name", "password1", "password2")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['password1'].label = _("Mot de passe")
        self.fields['password2'].label = _("Confirmation du mot de passe")
        for field_name in ('email', 'first_name', 'last_name', 'password1', 'password2'):
            self.fields[field_name].widget.attrs['class'] = 'form-control'

    def clean_email(self):
        return self.cleaned_data["email"].strip().lower()


class CustomUserChangeForm(UserChangeForm):
    class Meta:
        model = User
        fields = ("email", "first_name", "last_name")


class OwnerAccountProfileForm(CustomUserChangeForm):
    email = forms.EmailField(label=_("Adresse e-mail"))
    first_name = forms.CharField(label=_("First name"), required=False)
    last_name = forms.CharField(label=_("Last name"), required=False)

    class Meta(CustomUserChangeForm.Meta):
        fields = ("email", "first_name", "last_name")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        password_field = self.fields.get('password')
        if password_field is not None:
            password_field.widget = forms.HiddenInput()
            password_field.required = False
        for field_name in ('email', 'first_name', 'last_name'):
            self.fields[field_name].widget.attrs['class'] = 'form-control'

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if User.objects.exclude(pk=self.instance.pk).filter(email=email).exists():
            raise forms.ValidationError(_("A user with that email already exists."))
        return email


class OwnerFoodTruckFormMixin:
    text_placeholders = {
        'service_address_line_1': _('Street and number'),
        'service_address_line_2': _('Building, floor, landmark'),
        'service_postal_code': _('Postal code'),
        'service_city': _('City'),
        'service_country': _('Country'),
        'billing_address_line_1': _('Street and number'),
        'billing_address_line_2': _('Building, floor, landmark'),
        'billing_postal_code': _('Postal code'),
        'billing_city': _('City'),
        'billing_country': _('Country'),
        'billing_siret': '12345678901234',
        'billing_vat_number': 'FR12345678901',
    }

    def _apply_form_control_classes(self):
        for field in self.fields.values():
            existing_class = field.widget.attrs.get('class', '')
            if isinstance(field.widget, forms.Select):
                field.widget.attrs['class'] = f'{existing_class} form-select'.strip()
            elif isinstance(field.widget, forms.ClearableFileInput):
                field.widget.attrs['class'] = f'{existing_class} form-control'.strip()
            elif isinstance(field.widget, forms.Textarea):
                field.widget.attrs['class'] = f'{existing_class} form-control'.strip()
            else:
                field.widget.attrs['class'] = f'{existing_class} form-control'.strip()

        for field_name, placeholder in self.text_placeholders.items():
            if field_name in self.fields:
                self.fields[field_name].widget.attrs['placeholder'] = placeholder


class OwnerFoodTruckIdentityForm(OwnerFoodTruckFormMixin, forms.ModelForm):
    class Meta:
        model = FoodTruck
        fields = (
            'name',
            'description',
            'default_language',
            'price_display_mode',
            'logo',
            'primary_color',
            'secondary_color',
        )
        labels = {
            'name': _('Food truck name'),
            'description': _('Food truck description'),
            'default_language': _('Content language'),
            'price_display_mode': _('Displayed price mode'),
            'logo': _('Logo'),
            'primary_color': _('Primary color'),
            'secondary_color': _('Secondary color'),
        }
        widgets = {
            'description': forms.Textarea(attrs={'rows': 4, 'class': 'form-control'}),
            'default_language': forms.Select(attrs={'class': 'form-select'}),
            'price_display_mode': forms.Select(attrs={'class': 'form-select'}),
            'logo': forms.ClearableFileInput(attrs={'class': 'form-control'}),
            'primary_color': forms.TextInput(attrs={'class': 'form-control form-control-color', 'type': 'color'}),
            'secondary_color': forms.TextInput(attrs={'class': 'form-control form-control-color', 'type': 'color'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._apply_form_control_classes()


class OwnerFoodTruckServiceAddressForm(OwnerFoodTruckFormMixin, forms.ModelForm):
    class Meta:
        model = FoodTruck
        fields = (
            'service_address_line_1',
            'service_address_line_2',
            'service_postal_code',
            'service_city',
            'service_country',
        )
        labels = {
            'service_address_line_1': _('Base service address line 1'),
            'service_address_line_2': _('Base service address line 2'),
            'service_postal_code': _('Base service postal code'),
            'service_city': _('Base service city'),
            'service_country': _('Base service country'),
        }

    def __init__(self, *args, require_address=False, **kwargs):
        self.require_address = require_address
        super().__init__(*args, **kwargs)
        self._apply_form_control_classes()

    def clean(self):
        cleaned = super().clean()
        required_fields = (
            'service_address_line_1',
            'service_postal_code',
            'service_city',
            'service_country',
        )

        should_validate = self.require_address or any(cleaned.get(field_name) for field_name in self.Meta.fields)
        if not should_validate:
            return cleaned

        for field_name in self.Meta.fields:
            value = cleaned.get(field_name)
            if isinstance(value, str):
                cleaned[field_name] = value.strip()

        for field_name in required_fields:
            if not cleaned.get(field_name):
                self.add_error(field_name, _('This field is required.'))

        if self.errors:
            return cleaned

        self.instance.service_address_line_1 = cleaned['service_address_line_1']
        self.instance.service_address_line_2 = cleaned.get('service_address_line_2', '')
        self.instance.service_postal_code = cleaned['service_postal_code']
        self.instance.service_city = cleaned['service_city']
        self.instance.service_country = cleaned['service_country']

        try:
            self.instance.resolve_base_service_geodata(geocoding_service=LocationGeocodingService)
        except forms.ValidationError:
            raise
        except Exception as exc:
            raise forms.ValidationError(str(exc))

        cleaned['service_address_line_1'] = self.instance.service_address_line_1
        cleaned['service_address_line_2'] = self.instance.service_address_line_2
        cleaned['service_postal_code'] = self.instance.service_postal_code
        cleaned['service_city'] = self.instance.service_city
        cleaned['service_country'] = self.instance.service_country
        return cleaned

    def save(self, commit=True):
        instance = super().save(commit=False)
        if self.instance.latitude is not None and self.instance.longitude is not None:
            instance.latitude = self.instance.latitude
            instance.longitude = self.instance.longitude
        if commit:
            instance.save()
            self.save_m2m()
        return instance


class OwnerFoodTruckBillingForm(OwnerFoodTruckFormMixin, forms.ModelForm):
    class Meta:
        model = FoodTruck
        fields = (
            'legal_business_name',
            'billing_siret',
            'billing_vat_number',
            'billing_address_line_1',
            'billing_address_line_2',
            'billing_postal_code',
            'billing_city',
            'billing_country',
        )
        labels = {
            'legal_business_name': _('Official business name'),
            'billing_siret': _('SIRET'),
            'billing_vat_number': _('VAT number'),
            'billing_address_line_1': _('Official billing address line 1'),
            'billing_address_line_2': _('Official billing address line 2'),
            'billing_postal_code': _('Official billing postal code'),
            'billing_city': _('Official billing city'),
            'billing_country': _('Official billing country'),
        }

    def __init__(self, *args, require_billing=False, **kwargs):
        self.require_billing = require_billing
        super().__init__(*args, **kwargs)
        self._apply_form_control_classes()

    def clean_billing_siret(self):
        siret = (self.cleaned_data.get('billing_siret') or '').strip().replace(' ', '')
        if siret and (not siret.isdigit() or len(siret) != 14):
            raise forms.ValidationError(_('Enter a valid 14-digit SIRET number.'))
        return siret

    def clean(self):
        cleaned = super().clean()
        required_billing_fields = (
            'legal_business_name',
            'billing_siret',
            'billing_address_line_1',
            'billing_postal_code',
            'billing_city',
            'billing_country',
        )

        should_validate = self.require_billing or any(cleaned.get(field_name) for field_name in self.Meta.fields)
        if not should_validate:
            return cleaned

        for field_name in self.Meta.fields:
            value = cleaned.get(field_name)
            if isinstance(value, str):
                value = value.strip()
                cleaned[field_name] = value

        for field_name in required_billing_fields:
            if not cleaned.get(field_name):
                self.add_error(field_name, _('This field is required.'))

        return cleaned
