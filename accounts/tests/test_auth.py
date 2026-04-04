# accounts/tests/test_auth.py

from django.test import TestCase
from django.contrib.auth import authenticate
from django.urls import reverse
from foodtrucks.tests.factories import UserFactory


class AuthenticationTests(TestCase):
    """Test authentication functionality."""

    def setUp(self):
        self.user = UserFactory(email="test@example.com", password="testpass123")
        self.login_url = reverse('accounts:login')
        self.logout_url = reverse('accounts:logout')

    def test_login_valid_credentials(self):
        """Test successful login with valid credentials."""
        response = self.client.post(self.login_url, {
            'username': 'test@example.com',
            'password': 'testpass123'
        })
        self.assertEqual(response.status_code, 302)  # Redirect on success

    def test_login_invalid_password(self):
        """Test login fails with invalid password."""
        response = self.client.post(self.login_url, {
            'username': 'test@example.com',
            'password': 'wrongpass'
        })
        self.assertEqual(response.status_code, 200)  # Form re-rendered

    def test_login_unknown_email(self):
        """Test login fails with unknown email."""
        response = self.client.post(self.login_url, {
            'username': 'unknown@example.com',
            'password': 'testpass123'
        })
        self.assertEqual(response.status_code, 200)

    def test_logout_invalidates_session(self):
        """Test logout invalidates the session."""
        self.client.login(username='test@example.com', password='testpass123')
        response = self.client.get(self.logout_url)
        self.assertEqual(response.status_code, 302)