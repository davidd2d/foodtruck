# accounts/tests/test_views.py
import pytest
from django.urls import reverse
from django.core import mail
from django.contrib.auth import get_user_model

User = get_user_model()

@pytest.mark.django_db
def test_signup_valid(client):
    response = client.post(reverse("accounts:register"), {
        "email": "valid@intermas.com",
        "first_name": "Valid",
        "last_name": "User",
        "password1": "StrongPass123",
        "password2": "StrongPass123"
    })
    assert response.status_code == 302
    assert User.objects.filter(email="valid@intermas.com").exists()
    print(mail.outbox)
    assert len(mail.outbox) == 1
    assert "Confirm" in mail.outbox[0].subject

@pytest.mark.django_db
def test_signup_invalid_email(client):
    response = client.post(reverse("accounts:register"), {
        "email": "invalid@gmail.com",
        "first_name": "Invalid",
        "last_name": "User",
        "password1": "StrongPass123",
        "password2": "StrongPass123"
    })
    assert "email" in response.context["form"].errors
    assert "@intermas.com" in response.context["form"].errors['email'][0]
    assert User.objects.count() == 0

from accounts.forms import CustomUserCreationForm

def test_signup_invalid_email_form():
    form = CustomUserCreationForm(data={
        "email": "invalid@gmail.com",
        "first_name": "Invalid",
        "last_name": "User",
        "password1": "StrongPass123",
        "password2": "StrongPass123"
    })
    assert not form.is_valid()
    assert "email" in form.errors
    assert "intermas.com" in form.errors["email"][0]

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
