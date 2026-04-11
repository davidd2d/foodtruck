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
def test_user_creation_form_allows_any_email_domain():
    form_data = {
        "email": "jane@gmail.com",
        "first_name": "Jane",
        "last_name": "Doe",
        "password1": "StrongPass123",
        "password2": "StrongPass123",
    }
    form = CustomUserCreationForm(data=form_data)
    assert form.is_valid()

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

def test_user_creation_form_uses_only_password_and_confirmation_fields():
    form = CustomUserCreationForm()

    assert 'password' not in form.fields
    assert 'password1' in form.fields
    assert 'password2' in form.fields

@pytest.mark.django_db
def test_valid_user_change_form():
    form_data = {
        "email": "jane@intermas.com",
        "first_name": "Jane",
        "last_name": "Doe",
    }
    form = CustomUserChangeForm(data=form_data)
    assert form.is_valid()
