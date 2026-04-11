# accounts/tests/test_views.py
import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from django.core import mail
from django.contrib.auth import get_user_model
from unittest.mock import patch
from foodtrucks.tests.factories import FoodTruckFactory, UserFactory

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
        reverse('accounts:profile', kwargs={'slug': foodtruck.slug}),
        {
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
        reverse('accounts:profile', kwargs={'slug': foodtruck.slug}),
        {
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
        reverse('accounts:profile', kwargs={'slug': foodtruck.slug}),
        {
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
        reverse('accounts:profile', kwargs={'slug': foodtruck.slug}),
        {
            'save-foodtruck': '1',
            'name': 'Truck Renamed',
            'description': 'Nouvelle description',
            'default_language': 'fr',
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
def test_owner_profile_renaming_foodtruck_updates_slug_and_redirect(client):
    foodtruck = FoodTruckFactory(name='Old Truck Name')

    client.login(email=foodtruck.owner.email, password='password123')
    response = client.post(
        reverse('accounts:profile', kwargs={'slug': foodtruck.slug}),
        {
            'save-foodtruck': '1',
            'name': 'New Truck Name',
            'description': foodtruck.description,
            'default_language': foodtruck.default_language,
            'primary_color': foodtruck.primary_color,
            'secondary_color': foodtruck.secondary_color,
        },
        follow=False,
    )

    foodtruck.refresh_from_db()

    assert response.status_code == 302
    assert foodtruck.slug == 'new-truck-name'
    assert response.url == reverse('accounts:profile', kwargs={'slug': foodtruck.slug})


@pytest.mark.django_db
def test_owner_profile_renaming_foodtruck_generates_unique_slug(client):
    FoodTruckFactory(name='Existing Truck Name')
    foodtruck = FoodTruckFactory(name='Original Owner Truck')

    client.login(email=foodtruck.owner.email, password='password123')
    response = client.post(
        reverse('accounts:profile', kwargs={'slug': foodtruck.slug}),
        {
            'save-foodtruck': '1',
            'name': 'Existing Truck Name',
            'description': foodtruck.description,
            'default_language': foodtruck.default_language,
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
