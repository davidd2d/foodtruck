# apps/accounts/views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.utils.translation import gettext as _
from django.utils.http import urlsafe_base64_decode

from .utils import generate_email_confirmation_token, verify_email_confirmation_token
from .models import CustomUser

from django.contrib.auth import login, logout
from .forms import CustomUserCreationForm
from .utils import send_mail, send_confirmation_email  # déjà importé
from .tokens import email_confirmation_token_generator

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
    try:
        user = CustomUser.objects.get(email=request.GET.get("email"))
    except CustomUser.DoesNotExist:
        messages.error(request, _("Utilisateur introuvable."))
        return redirect("accounts:login")

    if email_confirmation_token_generator.check_token(user, token):
        user.email_verified = True
        user.is_active = True
        user.save()
        messages.success(request, _("Email confirmé avec succès."))
        return redirect("accounts:login")
    else:
        messages.error(request, _("Lien de confirmation invalide ou expiré."))
        return redirect("accounts:login")

def confirm_email(request, uidb64, token):
    try:
        uid = urlsafe_base64_decode(uidb64).decode()
        user = CustomUser.objects.get(pk=uid)
    except (TypeError, ValueError, OverflowError, CustomUser.DoesNotExist):
        user = None

    if user and email_confirmation_token_generator.check_token(user, token):
        user.email_verified = True
        user.is_active = True
        user.save()
        messages.success(request, _("Email confirmé avec succès."))
        return redirect("accounts:login")

    messages.error(request, _("Lien de confirmation invalide ou expiré."))
    return redirect("accounts:login")