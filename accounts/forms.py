# apps/accounts/forms.py
from django import forms
from django.contrib.auth.forms import UserCreationForm, UserChangeForm, AuthenticationForm
from django.utils.translation import gettext_lazy as _
from .models import User
from foodtrucks.models import FoodTruck

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


class OwnerFoodTruckProfileForm(forms.ModelForm):
    class Meta:
        model = FoodTruck
        fields = (
            'name',
            'description',
            'default_language',
            'logo',
            'primary_color',
            'secondary_color',
        )
        labels = {
            'name': _('Food truck name'),
            'description': _('Food truck description'),
            'default_language': _('Content language'),
            'logo': _('Logo'),
            'primary_color': _('Primary color'),
            'secondary_color': _('Secondary color'),
        }
        widgets = {
            'description': forms.Textarea(attrs={'rows': 4, 'class': 'form-control'}),
            'default_language': forms.Select(attrs={'class': 'form-select'}),
            'logo': forms.ClearableFileInput(attrs={'class': 'form-control'}),
            'primary_color': forms.TextInput(attrs={'class': 'form-control form-control-color', 'type': 'color'}),
            'secondary_color': forms.TextInput(attrs={'class': 'form-control form-control-color', 'type': 'color'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['name'].widget.attrs['class'] = 'form-control'
