# accounts/tests/test_models.py
import pytest
from django.contrib.auth import get_user_model
from django.db import IntegrityError

User = get_user_model()


@pytest.mark.django_db
def test_create_user():
    user = User.objects.create_user(
        email="user@intermas.com",
        password="testpass123",
        first_name="John",
        last_name="Doe"
    )
    assert user.email == "user@intermas.com"
    assert user.first_name == "John"
    assert user.last_name == "Doe"
    assert user.is_active is True
    assert user.is_staff is False
    assert user.is_superuser is False
    assert user.check_password("testpass123")


@pytest.mark.django_db
def test_create_superuser():
    admin_user = User.objects.create_superuser(
        email="admin@intermas.com",
        password="adminpass123",
        first_name="Admin",
        last_name="User"
    )
    assert admin_user.is_superuser is True
    assert admin_user.is_staff is True
    assert admin_user.is_active is True


@pytest.mark.django_db
def test_email_is_normalized():
    user = User.objects.create_user(
        email="User@Intermas.Com",
        password="testpass123",
        first_name="John",
        last_name="Doe"
    )
    assert user.email == "user@intermas.com"  # Entire email is normalized to lowercase


@pytest.mark.django_db
def test_user_str_representation():
    user = User.objects.create_user(
        email="jane@intermas.com",
        password="pass1234",
        first_name="Jane",
        last_name="Doe"
    )
    assert str(user) == "jane@intermas.com"


@pytest.mark.django_db
def test_email_required():
    with pytest.raises(ValueError):
        User.objects.create_user(email=None, password="testpass123")


@pytest.mark.django_db
def test_email_unique():
    User.objects.create_user(email="unique@test.com", password="testpass123")
    with pytest.raises(IntegrityError):
        User.objects.create_user(email="unique@test.com", password="testpass456")


@pytest.mark.django_db
def test_password_hashed():
    user = User.objects.create_user(email="hash@test.com", password="plaintext")
    assert user.password != "plaintext"
    assert user.check_password("plaintext")


@pytest.mark.django_db
def test_invalid_user_creation_missing_email():
    with pytest.raises(ValueError):
        User.objects.create_user(email="", password="testpass123")


@pytest.mark.django_db
def test_invalid_user_creation_duplicate_email():
    User.objects.create_user(email="dup@test.com", password="testpass123")
    with pytest.raises(IntegrityError):
        User.objects.create_user(email="dup@test.com", password="testpass456")
