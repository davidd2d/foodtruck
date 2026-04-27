# apps/accounts/views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.utils.translation import gettext as _
from django.contrib.auth.decorators import login_required
from django.db.models import Count

from django.contrib.auth import logout
from foodtrucks.models import FoodTruck
from orders.models import Ticket
from .models import User
from .forms import CustomUserCreationForm, OwnerAccountProfileForm, OwnerFoodTruckProfileForm
from .utils import send_confirmation_email, verify_email_confirmation_token

def register(request):
    if request.method == "POST":
        post_data = request.POST.copy()
        # Backward compatibility: accept a single "password" key and map it to
        # the Django UserCreationForm expected fields.
        if post_data.get('password') and not post_data.get('password1') and not post_data.get('password2'):
            post_data['password1'] = post_data['password']
            post_data['password2'] = post_data['password']

        form = CustomUserCreationForm(post_data)
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


@login_required
def profile_redirect(request):
    foodtruck = request.user.foodtrucks.order_by('created_at').first()
    if foodtruck is None:
        messages.error(request, _("No managed food truck found for your account."))
        return redirect('foodtrucks:foodtruck-list')
    return redirect('accounts:profile', slug=foodtruck.slug)


@login_required
def profile(request, slug):
    foodtruck = get_object_or_404(FoodTruck, slug=slug, owner=request.user)
    active_menu = foodtruck.menus.filter(is_active=True).first()
    categories = active_menu.categories.order_by('display_order', 'name') if active_menu else []

    account_form = OwnerAccountProfileForm(instance=request.user)
    foodtruck_form = OwnerFoodTruckProfileForm(instance=foodtruck)

    if request.method == "POST":
        if 'save-foodtruck' in request.POST:
            foodtruck_form = OwnerFoodTruckProfileForm(request.POST, request.FILES, instance=foodtruck)
            if foodtruck_form.is_valid():
                foodtruck_form.save()
                messages.success(request, _("Your food truck has been updated."))
                return redirect('accounts:profile', slug=foodtruck.slug)
        else:
            previous_email = request.user.email
            account_form = OwnerAccountProfileForm(request.POST, instance=request.user)
            if account_form.is_valid():
                account = account_form.save(commit=False)
                account.username = account.email
                email_changed = account.email != previous_email

                if email_changed:
                    account.email_verified = False

                account.save()

                if email_changed:
                    send_confirmation_email(account, request)
                    messages.success(request, _("Your account has been updated. Please confirm your new email address."))
                else:
                    messages.success(request, _("Your account has been updated."))
                return redirect('accounts:profile', slug=foodtruck.slug)

    owner_ticket_stats = Ticket.objects.filter(order__food_truck=foodtruck).aggregate(
        issued_tickets_count=Count('id')
    )
    my_ticket_count = Ticket.objects.filter(order__food_truck=foodtruck, order__user=request.user).count()

    return render(
        request,
        "accounts/profile.html",
        {
            "account_form": account_form,
            "foodtruck_form": foodtruck_form,
            "foodtruck": foodtruck,
            "categories": categories,
            "issued_tickets_count": owner_ticket_stats['issued_tickets_count'] or 0,
            "my_ticket_count": my_ticket_count,
        },
    )
