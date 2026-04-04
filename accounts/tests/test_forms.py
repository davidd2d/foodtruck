# accounts/tests/test_forms.py
import pytest
from accounts.forms import CustomUserCreationForm, CustomUserChangeForm

@pytest.mark.django_db
def test_valid_user_creation_form():
    form_data = {
        "email": "jane@intermas.com",
        "first_name": "Jane",
        "last_name": "Doe",
        "password1": "StrongPass123",
        "password2": "StrongPass123",
    }
    form = CustomUserCreationForm(data=form_data)
    assert form.is_valid()

@pytest.mark.django_db
def test_invalid_email_domain_user_creation_form():
    form_data = {
        "email": "jane@gmail.com",
        "first_name": "Jane",
        "last_name": "Doe",
        "password1": "StrongPass123",
        "password2": "StrongPass123",
    }
    form = CustomUserCreationForm(data=form_data)
    assert not form.is_valid()
    assert "@intermas.com" in form.errors["email"][0]

@pytest.mark.django_db
def test_password_mismatch_user_creation_form():
    form_data = {
        "email": "jane@intermas.com",
        "first_name": "Jane",
        "last_name": "Doe",
        "password1": "StrongPass123",
        "password2": "WrongPass456",
    }
    form = CustomUserCreationForm(data=form_data)
    assert not form.is_valid()
    assert "password2" in form.errors

@pytest.mark.django_db
def test_valid_user_change_form():
    form_data = {
        "email": "jane@intermas.com",
        "first_name": "Jane",
        "last_name": "Doe",
    }
    form = CustomUserChangeForm(data=form_data)
    assert form.is_valid()
