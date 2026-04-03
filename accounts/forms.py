# apps/accounts/forms.py
from django import forms
from django.contrib.auth.forms import UserCreationForm, UserChangeForm, AuthenticationForm
from django.utils.translation import gettext_lazy as _
from .models import CustomUser

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


class CustomUserCreationForm(UserCreationForm):
    email = forms.EmailField(label=_("Adresse e-mail"), help_text=_("Utilisez une adresse @intermas.com"))

    class Meta:
        model = CustomUser
        fields = ("email", "first_name", "last_name", "password1", "password2")

    def clean_email(self):
        email = self.cleaned_data["email"]
        if not email.endswith("@intermas.com"):
            raise forms.ValidationError(_("Seuls les addresses email @intermas.com sont autorisées."))
        return email


class CustomUserChangeForm(UserChangeForm):
    class Meta:
        model = CustomUser
        fields = ("email", "first_name", "last_name")