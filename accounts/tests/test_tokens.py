# accounts/tests/test_tokens.py
import pytest
from django.contrib.auth import get_user_model
from accounts.tokens import email_confirmation_token_generator

User = get_user_model()

@pytest.mark.django_db
def test_token_generation_and_validation():
    user = User.objects.create_user(
        email="jane@intermas.com",
        password="pass123",
        first_name="Jane",
        last_name="Doe"
    )
    user.is_active = True
    user.save()

    token = email_confirmation_token_generator.make_token(user)
    
    # NE PAS modifier email_verified ici !
    is_valid = email_confirmation_token_generator.check_token(user, token)

    assert is_valid is True

@pytest.mark.django_db
def test_token_invalid_after_password_change():
    user = User.objects.create_user(
        email="john@intermas.com",
        password="pass123",
        first_name="John",
        last_name="Smith"
    )
    token = email_confirmation_token_generator.make_token(user)
    user.set_password("newpass456")
    user.save()
    is_valid = email_confirmation_token_generator.check_token(user, token)
    assert is_valid is False

@pytest.mark.django_db
def test_token_invalid_after_email_verified():
    user = User.objects.create_user(
        email="bob@intermas.com",
        password="pass123",
        first_name="Bob",
        last_name="Marley"
    )
    token = email_confirmation_token_generator.make_token(user)
    user.email_verified = True
    user.save()
    is_valid = email_confirmation_token_generator.check_token(user, token)
    assert is_valid is False
