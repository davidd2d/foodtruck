# accounts/tests/test_views.py
import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from django.core import mail
from django.contrib.auth import get_user_model
from unittest.mock import patch
from decimal import Decimal
from foodtrucks.tests.factories import FoodTruckFactory, UserFactory, PlanFactory

User = get_user_model()

@pytest.mark.django_db
def test_signup_valid(client):
    response = client.post(reverse("accounts:register"), {
        "email": "valid@gmail.com",
        "first_name": "Valid",
        "last_name": "User",
        "password1": "StrongPass123",
        "password2": "StrongPass123"
    })
    assert response.status_code == 302
    assert User.objects.filter(email="valid@gmail.com").exists()
    print(mail.outbox)
    assert len(mail.outbox) == 1
    assert "Confirm" in mail.outbox[0].subject

@pytest.mark.django_db
def test_signup_accepts_non_intermas_email(client):
    response = client.post(reverse("accounts:register"), {
        "email": "invalid@gmail.com",
        "first_name": "Invalid",
        "last_name": "User",
        "password1": "StrongPass123",
        "password2": "StrongPass123"
    })
    assert response.status_code == 302
    assert User.objects.filter(email="invalid@gmail.com").exists()

from accounts.forms import CustomUserCreationForm

@pytest.mark.django_db
def test_signup_invalid_email_form():
    form = CustomUserCreationForm(data={
        "email": "invalid@gmail.com",
        "first_name": "Invalid",
        "last_name": "User",
        "password1": "StrongPass123",
        "password2": "StrongPass123"
    })
    assert form.is_valid()

from django.utils.http import urlsafe_base64_encode
from django.utils.encoding import force_bytes

@pytest.mark.django_db
def test_email_confirmation(client):
    user = User.objects.create_user(
        email="confirm@intermas.com", password="testpass", first_name="C", last_name="U"
    )

    from accounts.utils import generate_email_confirmation_token

    token = generate_email_confirmation_token(user)
    url = reverse("accounts:confirm_email", args=[token])
    response = client.get(url)

    user.refresh_from_db()
    assert response.status_code == 302
    assert user.email_verified is True

@pytest.mark.django_db
def test_password_reset_flow(client):
    user = User.objects.create_user(
        email="reset@intermas.com", password="oldpass123", first_name="Reset", last_name="User"
    )
    response = client.post(reverse("accounts:password_reset"), {"email": "reset@intermas.com"})
    assert response.status_code == 302
    assert len(mail.outbox) == 1
    assert "Réinitialisation du mot de passe" in mail.outbox[0].subject


@pytest.mark.django_db
def test_owner_profile_redirects_to_first_foodtruck(client):
    foodtruck = FoodTruckFactory()

    client.login(email=foodtruck.owner.email, password='password123')
    response = client.get(reverse('accounts:profile-redirect'))

    assert response.status_code == 302
    assert response.url == reverse('accounts:profile', kwargs={'slug': foodtruck.slug})


@pytest.mark.django_db
def test_owner_profile_page_uses_foodtruck_slug(client):
    foodtruck = FoodTruckFactory()

    client.login(email=foodtruck.owner.email, password='password123')
    response = client.get(reverse('accounts:profile', kwargs={'slug': foodtruck.slug}))

    assert response.status_code == 200
    assert foodtruck.slug in response.content.decode()


@pytest.mark.django_db
def test_owner_profile_updates_account(client):
    foodtruck = FoodTruckFactory()
    original_email = foodtruck.owner.email

    client.login(email=foodtruck.owner.email, password='password123')
    response = client.post(
        reverse('accounts:profile-section', kwargs={'slug': foodtruck.slug, 'section': 'account'}),
        {
            'save-account': '1',
            'email': original_email,
            'first_name': 'Owner',
            'last_name': 'Updated',
        },
        follow=True,
    )

    foodtruck.owner.refresh_from_db()

    assert response.status_code == 200
    assert foodtruck.owner.email == original_email
    assert foodtruck.owner.first_name == 'Owner'
    assert foodtruck.owner.last_name == 'Updated'
    assert foodtruck.owner.username == original_email
    assert foodtruck.owner.email_verified is True


@pytest.mark.django_db
@patch('accounts.views.send_confirmation_email')
def test_owner_profile_email_change_restarts_confirmation(mock_send, client):
    foodtruck = FoodTruckFactory()
    foodtruck.owner.email_verified = True
    foodtruck.owner.save(update_fields=['email_verified'])

    client.login(email=foodtruck.owner.email, password='password123')
    response = client.post(
        reverse('accounts:profile-section', kwargs={'slug': foodtruck.slug, 'section': 'account'}),
        {
            'save-account': '1',
            'email': 'renewed@intermas.com',
            'first_name': 'Owner',
            'last_name': 'Updated',
        },
        follow=True,
    )

    foodtruck.owner.refresh_from_db()

    assert response.status_code == 200
    assert foodtruck.owner.email == 'renewed@intermas.com'
    assert foodtruck.owner.username == 'renewed@intermas.com'
    assert foodtruck.owner.email_verified is False
    mock_send.assert_called_once()
    sent_user, sent_request = mock_send.call_args.args
    assert sent_user == foodtruck.owner
    assert hasattr(sent_request, 'build_absolute_uri')


@pytest.mark.django_db
@patch('accounts.views.send_confirmation_email')
def test_owner_profile_name_only_change_does_not_send_confirmation(mock_send, client):
    foodtruck = FoodTruckFactory()
    original_email = foodtruck.owner.email

    client.login(email=foodtruck.owner.email, password='password123')
    response = client.post(
        reverse('accounts:profile-section', kwargs={'slug': foodtruck.slug, 'section': 'account'}),
        {
            'save-account': '1',
            'email': original_email,
            'first_name': 'Changed',
            'last_name': 'Owner',
        },
        follow=True,
    )

    foodtruck.owner.refresh_from_db()

    assert response.status_code == 200
    assert foodtruck.owner.email == original_email
    assert foodtruck.owner.email_verified is True
    mock_send.assert_not_called()


@pytest.mark.django_db
def test_owner_profile_updates_foodtruck_details(client, settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path
    foodtruck = FoodTruckFactory()
    logo_file = SimpleUploadedFile(
        'logo.gif',
        b'GIF89a\x01\x00\x01\x00\x80\x00\x00\x00\x00\x00\xff\xff\xff!\xf9\x04\x01\x00\x00\x00\x00,\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;',
        content_type='image/gif',
    )

    client.login(email=foodtruck.owner.email, password='password123')
    response = client.post(
        reverse('accounts:profile-section', kwargs={'slug': foodtruck.slug, 'section': 'identity'}),
        {
            'save-identity': '1',
            'name': 'Truck Renamed',
            'description': 'Nouvelle description',
            'default_language': 'fr',
            'price_display_mode': foodtruck.price_display_mode,
            'primary_color': '#112233',
            'secondary_color': '#445566',
            'logo': logo_file,
        },
        follow=True,
    )

    foodtruck.refresh_from_db()

    assert response.status_code == 200
    assert foodtruck.name == 'Truck Renamed'
    assert foodtruck.description == 'Nouvelle description'
    assert foodtruck.default_language == 'fr'
    assert foodtruck.primary_color == '#112233'
    assert foodtruck.secondary_color == '#445566'
    assert foodtruck.logo.name.endswith('logo.gif')


@pytest.mark.django_db
@patch('accounts.forms.LocationGeocodingService.geocode_address')
def test_owner_profile_updates_base_location(mock_geocode, client):
    foodtruck = FoodTruckFactory(latitude=40.7128, longitude=-74.0060)
    mock_geocode.return_value = (Decimal('45.764043'), Decimal('4.835659'))

    client.login(email=foodtruck.owner.email, password='password123')
    response = client.post(
        reverse('accounts:profile-section', kwargs={'slug': foodtruck.slug, 'section': 'service'}),
        {
            'save-service-address': '1',
            'service_address_line_1': '5 Place Bellecour',
            'service_address_line_2': '',
            'service_postal_code': '69002',
            'service_city': 'Lyon',
            'service_country': 'France',
        },
        follow=True,
    )

    foodtruck.refresh_from_db()

    assert response.status_code == 200
    assert float(foodtruck.latitude) == pytest.approx(45.764043)
    assert float(foodtruck.longitude) == pytest.approx(4.835659)
    mock_geocode.assert_called_once_with('5 Place Bellecour, 69002 Lyon, France')


@pytest.mark.django_db
def test_owner_profile_updates_billing_details(client):
    foodtruck = FoodTruckFactory()

    client.login(email=foodtruck.owner.email, password='password123')
    response = client.post(
        reverse('accounts:profile-section', kwargs={'slug': foodtruck.slug, 'section': 'billing'}),
        {
            'save-billing': '1',
            'legal_business_name': 'Cucina di Pastaz SAS',
            'billing_siret': '12345678901234',
            'billing_vat_number': 'FR12345678901',
            'billing_address_line_1': '12 Rue du Louvre',
            'billing_address_line_2': '',
            'billing_postal_code': '75001',
            'billing_city': 'Paris',
            'billing_country': 'France',
        },
        follow=True,
    )

    foodtruck.refresh_from_db()

    assert response.status_code == 200
    assert foodtruck.legal_business_name == 'Cucina di Pastaz SAS'
    assert foodtruck.billing_siret == '12345678901234'
    assert foodtruck.billing_city == 'Paris'


@pytest.mark.django_db
def test_owner_profile_billing_is_optional_without_ordering_service(client):
    foodtruck = FoodTruckFactory()
    optional_plan = PlanFactory(code='starter-no-ordering', name='Starter', allows_ordering=False)
    foodtruck.subscription.plan = optional_plan
    foodtruck.subscription.save(update_fields=['plan'])

    client.login(email=foodtruck.owner.email, password='password123')
    response = client.post(
        reverse('accounts:profile-section', kwargs={'slug': foodtruck.slug, 'section': 'billing'}),
        {
            'save-billing': '1',
            'legal_business_name': '',
            'billing_siret': '',
            'billing_vat_number': '',
            'billing_address_line_1': '',
            'billing_address_line_2': '',
            'billing_postal_code': '',
            'billing_city': '',
            'billing_country': '',
        },
        follow=False,
    )

    assert response.status_code == 302
    assert response.url == reverse('accounts:profile-section', kwargs={'slug': foodtruck.slug, 'section': 'billing'})


@pytest.mark.django_db
def test_owner_profile_hides_non_relevant_optional_sections(client):
    foodtruck = FoodTruckFactory()
    optional_plan = PlanFactory(code='starter-hidden-sections', name='Starter Hidden', allows_ordering=False)
    foodtruck.subscription.plan = optional_plan
    foodtruck.subscription.save(update_fields=['plan'])

    client.login(email=foodtruck.owner.email, password='password123')
    response = client.get(reverse('accounts:profile-section', kwargs={'slug': foodtruck.slug, 'section': 'identity'}))

    assert response.status_code == 200
    html = response.content.decode()
    assert reverse('accounts:profile-section', kwargs={'slug': foodtruck.slug, 'section': 'identity'}) in html
    assert reverse('accounts:profile-section', kwargs={'slug': foodtruck.slug, 'section': 'account'}) in html
    assert reverse('accounts:profile-section', kwargs={'slug': foodtruck.slug, 'section': 'service'}) not in html
    assert reverse('accounts:profile-section', kwargs={'slug': foodtruck.slug, 'section': 'billing'}) not in html


@pytest.mark.django_db
def test_owner_profile_identity_redirects_to_next_required_step(client):
    foodtruck = FoodTruckFactory()

    client.login(email=foodtruck.owner.email, password='password123')
    response = client.post(
        reverse('accounts:profile-section', kwargs={'slug': foodtruck.slug, 'section': 'identity'}),
        {
            'save-identity': '1',
            'name': 'Truck Renamed',
            'description': 'Nouvelle description',
            'default_language': 'fr',
            'price_display_mode': foodtruck.price_display_mode,
            'primary_color': '#112233',
            'secondary_color': '#445566',
        },
        follow=False,
    )

    foodtruck.refresh_from_db()

    assert response.status_code == 302
    assert response.url == reverse('accounts:profile-section', kwargs={'slug': foodtruck.slug, 'section': 'service'})


@pytest.mark.django_db
@patch('accounts.forms.LocationGeocodingService.geocode_address')
def test_owner_profile_service_redirects_to_billing_when_still_required(mock_geocode, client):
    foodtruck = FoodTruckFactory()
    mock_geocode.return_value = (Decimal('45.764043'), Decimal('4.835659'))

    client.login(email=foodtruck.owner.email, password='password123')
    response = client.post(
        reverse('accounts:profile-section', kwargs={'slug': foodtruck.slug, 'section': 'service'}),
        {
            'save-service-address': '1',
            'service_address_line_1': '5 Place Bellecour',
            'service_address_line_2': '',
            'service_postal_code': '69002',
            'service_city': 'Lyon',
            'service_country': 'France',
        },
        follow=False,
    )

    assert response.status_code == 302
    assert response.url == reverse('accounts:profile-section', kwargs={'slug': foodtruck.slug, 'section': 'billing'})


@pytest.mark.django_db
@patch('accounts.forms.LocationGeocodingService.geocode_address')
def test_owner_profile_renaming_foodtruck_updates_slug_and_redirect(mock_geocode, client):
    foodtruck = FoodTruckFactory(name='Old Truck Name')

    client.login(email=foodtruck.owner.email, password='password123')
    response = client.post(
        reverse('accounts:profile-section', kwargs={'slug': foodtruck.slug, 'section': 'identity'}),
        {
            'save-identity': '1',
            'name': 'New Truck Name',
            'description': foodtruck.description,
            'default_language': foodtruck.default_language,
            'price_display_mode': foodtruck.price_display_mode,
            'primary_color': foodtruck.primary_color,
            'secondary_color': foodtruck.secondary_color,
        },
        follow=False,
    )

    foodtruck.refresh_from_db()

    assert response.status_code == 302
    assert foodtruck.slug == 'new-truck-name'
    assert response.url == reverse('accounts:profile-section', kwargs={'slug': foodtruck.slug, 'section': 'service'})


@pytest.mark.django_db
@patch('accounts.forms.LocationGeocodingService.geocode_address')
def test_owner_profile_renaming_foodtruck_generates_unique_slug(mock_geocode, client):
    FoodTruckFactory(name='Existing Truck Name')
    foodtruck = FoodTruckFactory(name='Original Owner Truck')

    client.login(email=foodtruck.owner.email, password='password123')
    response = client.post(
        reverse('accounts:profile-section', kwargs={'slug': foodtruck.slug, 'section': 'identity'}),
        {
            'save-identity': '1',
            'name': 'Existing Truck Name',
            'description': foodtruck.description,
            'default_language': foodtruck.default_language,
            'price_display_mode': foodtruck.price_display_mode,
            'primary_color': foodtruck.primary_color,
            'secondary_color': foodtruck.secondary_color,
        },
        follow=False,
    )

    foodtruck.refresh_from_db()

    assert response.status_code == 302
    assert foodtruck.slug.startswith('existing-truck-name')
    assert foodtruck.slug != 'existing-truck-name'


@pytest.mark.django_db
def test_owner_profile_for_other_foodtruck_returns_404(client):
    foodtruck = FoodTruckFactory()
    other_owner = UserFactory(is_foodtruck_owner=True)

    client.login(email=other_owner.email, password='password123')
    response = client.get(reverse('accounts:profile', kwargs={'slug': foodtruck.slug}))

    assert response.status_code == 404
