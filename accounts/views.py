# apps/accounts/views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.utils.translation import gettext_lazy as _
from django.contrib.auth.decorators import login_required
from django.db.models import Count
from django.http import Http404
from django.urls import reverse

from django.contrib.auth import logout
from foodtrucks.models import FoodTruck
from orders.models import Ticket
from .models import User
from .forms import (
    CustomUserCreationForm,
    OwnerAccountProfileForm,
    OwnerFoodTruckIdentityForm,
    OwnerFoodTruckServiceAddressForm,
    OwnerFoodTruckBillingForm,
)
from .utils import send_confirmation_email, verify_email_confirmation_token


PROFILE_SECTIONS = {
    'identity': {
        'title': _('Food truck identity'),
        'description': _('Update branding, public description, display language, and pricing mode.'),
        'submit_label': _('Save identity'),
    },
    'service': {
        'title': _('Base service address'),
        'description': _('Define the operational base address used to derive default GPS coordinates.'),
        'submit_label': _('Save service address'),
    },
    'billing': {
        'title': _('Billing information'),
        'description': _('Provide the legal information required for invoicing and contracted payment services.'),
        'submit_label': _('Save billing information'),
    },
    'account': {
        'title': _('Account details'),
        'description': _('Manage the owner account linked to this food truck.'),
        'submit_label': _('Save changes'),
    },
}


def _detect_profile_section(request, section=None):
    if request.method == 'POST':
        if 'save-account' in request.POST:
            return 'account'
        if 'save-service-address' in request.POST:
            return 'service'
        if 'save-billing' in request.POST:
            return 'billing'
        if 'save-identity' in request.POST or 'save-foodtruck' in request.POST:
            return 'identity'
    return section or 'identity'


def _build_profile_sections(foodtruck, slug):
    service_required = foodtruck.requires_service_profile()
    billing_required = foodtruck.requires_billing_profile()
    return [
        {
            'key': 'identity',
            'title': _('Identity'),
            'url': reverse('accounts:profile-section', kwargs={'slug': slug, 'section': 'identity'}),
            'required': True,
            'complete': bool(foodtruck.name and foodtruck.default_language),
            'visible': True,
        },
        {
            'key': 'service',
            'title': _('Service address'),
            'url': reverse('accounts:profile-section', kwargs={'slug': slug, 'section': 'service'}),
            'required': service_required,
            'complete': foodtruck.has_completed_service_profile(),
            'visible': service_required,
        },
        {
            'key': 'billing',
            'title': _('Billing'),
            'url': reverse('accounts:profile-section', kwargs={'slug': slug, 'section': 'billing'}),
            'required': billing_required,
            'complete': foodtruck.has_completed_billing_profile(),
            'visible': billing_required,
        },
        {
            'key': 'account',
            'title': _('Owner account'),
            'url': reverse('accounts:profile-section', kwargs={'slug': slug, 'section': 'account'}),
            'required': True,
            'complete': bool(foodtruck.owner.email),
            'visible': True,
        },
    ]


def _get_next_incomplete_profile_section(foodtruck, slug, current_section):
    sections = _build_profile_sections(foodtruck, slug)
    current_index = next((index for index, section in enumerate(sections) if section['key'] == current_section), 0)

    for section in sections[current_index + 1:]:
        if section['required'] and not section['complete']:
            return section['key']

    for section in sections:
        if section['required'] and not section['complete']:
            return section['key']

    return current_section


def _get_profile_form(foodtruck, user, section, post_data=None, files_data=None):
    if section == 'identity':
        return OwnerFoodTruckIdentityForm(
            post_data,
            files_data,
            instance=foodtruck,
        )
    if section == 'service':
        return OwnerFoodTruckServiceAddressForm(
            post_data,
            instance=foodtruck,
            require_address=foodtruck.requires_service_profile(),
        )
    if section == 'billing':
        return OwnerFoodTruckBillingForm(
            post_data,
            instance=foodtruck,
            require_billing=foodtruck.requires_billing_profile(),
        )
    return OwnerAccountProfileForm(post_data, instance=user)

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
def profile(request, slug, section='identity'):
    foodtruck = get_object_or_404(FoodTruck, slug=slug, owner=request.user)
    current_section = _detect_profile_section(request, section)
    if current_section not in PROFILE_SECTIONS:
        raise Http404

    active_menu = foodtruck.menus.filter(is_active=True).first()
    categories = active_menu.categories.order_by('display_order', 'name') if active_menu else []

    profile_form = _get_profile_form(
        foodtruck,
        request.user,
        current_section,
        request.POST if request.method == 'POST' else None,
        request.FILES if request.method == 'POST' else None,
    )

    if request.method == "POST":
        if current_section == 'account':
            previous_email = request.user.email
            if profile_form.is_valid():
                account = profile_form.save(commit=False)
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
                next_section = _get_next_incomplete_profile_section(foodtruck, foodtruck.slug, current_section)
                return redirect('accounts:profile-section', slug=foodtruck.slug, section=next_section)
        else:
            if profile_form.is_valid():
                profile_form.save()
                foodtruck.refresh_from_db()
                if current_section == 'identity':
                    messages.success(request, _("Your food truck identity has been updated."))
                elif current_section == 'service':
                    messages.success(request, _("Your base service address has been updated."))
                else:
                    messages.success(request, _("Your billing information has been updated."))
                next_section = _get_next_incomplete_profile_section(foodtruck, foodtruck.slug, current_section)
                return redirect('accounts:profile-section', slug=foodtruck.slug, section=next_section)

    owner_ticket_stats = Ticket.objects.filter(order__food_truck=foodtruck).aggregate(
        issued_tickets_count=Count('id')
    )
    my_ticket_count = Ticket.objects.filter(order__food_truck=foodtruck, order__user=request.user).count()
    profile_sections = _build_profile_sections(foodtruck, foodtruck.slug)

    return render(
        request,
        "accounts/profile.html",
        {
            "profile_form": profile_form,
            "foodtruck": foodtruck,
            "categories": categories,
            "issued_tickets_count": owner_ticket_stats['issued_tickets_count'] or 0,
            "my_ticket_count": my_ticket_count,
            "profile_sections": profile_sections,
            "current_profile_section": current_section,
            "current_profile_section_meta": PROFILE_SECTIONS[current_section],
        },
    )
