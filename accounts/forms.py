# apps/accounts/forms.py
from django import forms
from django.contrib.auth.forms import UserCreationForm, UserChangeForm, AuthenticationForm
from django.utils.translation import gettext_lazy as _
from .models import User

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
    email = forms.EmailField(label=_("Adresse e-mail"), help_text=_("Utilisez une adresse @intermas.com"))
    password = forms.CharField(label=_("Mot de passe"), widget=forms.PasswordInput, required=False)

    class Meta:
        model = User
        fields = ("email", "first_name", "last_name", "password", "password1", "password2")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['password1'].required = False
        self.fields['password2'].required = False
        if self.data.get('password') and not self.data.get('password1'):
            data = self.data.copy()
            data['password1'] = data['password']
            data['password2'] = data['password']
            self.data = data

    def clean_email(self):
        email = self.cleaned_data["email"]
        if not email.endswith("@intermas.com"):
            raise forms.ValidationError(_("Seuls les addresses email @intermas.com sont autorisées."))
        return email


class CustomUserChangeForm(UserChangeForm):
    class Meta:
        model = User
        fields = ("email", "first_name", "last_name")