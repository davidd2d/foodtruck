# apps/accounts/views.py
from django.shortcuts import render, redirect
from django.contrib import messages
from django.utils.translation import gettext as _

from django.contrib.auth import logout
from .models import User
from .forms import CustomUserCreationForm
from .utils import send_confirmation_email, verify_email_confirmation_token

def register(request):
    if request.method == "POST":
        form = CustomUserCreationForm(request.POST)
        print("Création d'un nouvel utilisateur")
        if form.is_valid():
            user = form.save(commit=False)
            user.is_active = True  # Permet la connexion après confirmation
            user.save()
            send_confirmation_email(user, request)
            messages.success(request, _("Un e-mail de confirmation vous a été envoyé."))
            return redirect("accounts:login")
        else:
            messages.error(request, _("Votre demande ne peut aboutir."))
    else:
        form = CustomUserCreationForm()
    return render(request, "accounts/register.html", {"form": form})

# Option 1 : redirection directe
def signup(request):
    return register(request)

def logout_view(request):
    logout(request)
    messages.success(request, _("You have been logged out."))
    return redirect("accounts:login")  # ou "home" selon ton point d’entrée

def confirm_email(request, token):
    user_pk = verify_email_confirmation_token(token)
    if not user_pk:
        messages.error(request, _("Lien de confirmation invalide ou expiré."))
        return redirect("accounts:login")

    try:
        user = User.objects.get(pk=user_pk)
    except User.DoesNotExist:
        messages.error(request, _("Utilisateur introuvable."))
        return redirect("accounts:login")

    user.email_verified = True
    user.is_active = True
    user.save()
    messages.success(request, _("Email confirmé avec succès."))
    return redirect("accounts:login")

