import pytest
from datetime import timedelta
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken
from foodtrucks.tests.factories import UserFactory

pytestmark = pytest.mark.django_db


@pytest.fixture
def client():
    return APIClient()


@pytest.fixture
def user():
    return UserFactory(password='testpass123')


def test_login_returns_access_and_refresh(client, user):
    response = client.post(
        reverse('accounts_api:login'),
        {'email': user.email, 'password': 'testpass123'},
        format='json',
    )
    assert response.status_code == 200
    assert 'access' in response.data
    assert 'refresh' in response.data
    assert response.data['user']['email'] == user.email


def test_login_rejects_invalid_credentials(client, user):
    response = client.post(
        reverse('accounts_api:login'),
        {'email': user.email, 'password': 'wrongpass'},
        format='json',
    )
    assert response.status_code == 401
    assert 'access' not in response.data
    assert 'refresh' not in response.data


def test_authenticated_request_with_valid_token(client, user):
    login_response = client.post(
        reverse('accounts_api:login'),
        {'email': user.email, 'password': 'testpass123'},
        format='json',
    )
    access = login_response.data['access']
    refresh = login_response.data['refresh']

    client.credentials(HTTP_AUTHORIZATION=f'Bearer {access}')
    response = client.post(
        reverse('accounts_api:logout'),
        {'refresh': refresh},
        format='json',
    )
    assert response.status_code == 205


def test_invalid_token_is_rejected(client):
    client.credentials(HTTP_AUTHORIZATION='Bearer malformed.token.value')
    response = client.post(reverse('accounts_api:logout'), {'refresh': 'invalid'}, format='json')
    assert response.status_code == 403


def test_token_expiration_is_enforced(client, user):
    login_response = client.post(
        reverse('accounts_api:login'),
        {'email': user.email, 'password': 'testpass123'},
        format='json',
    )
    refresh = login_response.data['refresh']
    expired_access = AccessToken.for_user(user)
    expired_access.set_exp(from_time=timezone.now() - timedelta(minutes=10))

    client.credentials(HTTP_AUTHORIZATION=f'Bearer {str(expired_access)}')
    response = client.post(reverse('accounts_api:logout'), {'refresh': refresh}, format='json')
    assert response.status_code == 403


def test_refresh_rotates_tokens_and_old_token_is_invalid(client, user):
    login_response = client.post(
        reverse('accounts_api:login'),
        {'email': user.email, 'password': 'testpass123'},
        format='json',
    )
    old_refresh = login_response.data['refresh']

    refresh_response = client.post(
        reverse('accounts_api:refresh'),
        {'refresh': old_refresh},
        format='json',
    )
    assert refresh_response.status_code == 200
    assert 'access' in refresh_response.data
    assert 'refresh' in refresh_response.data
    new_refresh = refresh_response.data['refresh']
    assert new_refresh != old_refresh

    reuse_response = client.post(
        reverse('accounts_api:refresh'),
        {'refresh': old_refresh},
        format='json',
    )
    assert reuse_response.status_code == 401


def test_logout_blacklists_refresh_token(client, user):
    login_response = client.post(
        reverse('accounts_api:login'),
        {'email': user.email, 'password': 'testpass123'},
        format='json',
    )
    access = login_response.data['access']
    refresh = login_response.data['refresh']

    client.credentials(HTTP_AUTHORIZATION=f'Bearer {access}')
    logout_response = client.post(reverse('accounts_api:logout'), {'refresh': refresh}, format='json')
    assert logout_response.status_code == 205

    refresh_response = client.post(reverse('accounts_api:refresh'), {'refresh': refresh}, format='json')
    assert refresh_response.status_code == 401


def test_no_token_cannot_access_protected_endpoint(client):
    response = client.post(reverse('accounts_api:logout'), {'refresh': 'ignored'}, format='json')
    assert response.status_code == 403
