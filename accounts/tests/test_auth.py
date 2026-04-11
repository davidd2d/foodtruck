# accounts/tests/test_auth.py

from django.test import TestCase
from django.contrib.auth import authenticate
from django.urls import reverse
from foodtrucks.tests.factories import UserFactory
from foodtrucks.tests.factories import FoodTruckFactory
from unittest.mock import patch


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

    @patch('accounts.views.send_confirmation_email')
    def test_email_change_requires_reconfirmation_before_next_login(self, mock_send):
        foodtruck = FoodTruckFactory(owner=self.user)
        self.user.email_verified = True
        self.user.save(update_fields=['email_verified'])

        self.client.login(username='test@example.com', password='testpass123')
        response = self.client.post(
            reverse('accounts:profile', kwargs={'slug': foodtruck.slug}),
            {
                'save-account': '1',
                'email': 'newaddress@intermas.com',
                'first_name': self.user.first_name,
                'last_name': self.user.last_name,
            },
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.user.refresh_from_db()
        self.assertFalse(self.user.email_verified)

        self.client.logout()
        login_response = self.client.post(self.login_url, {
            'username': 'newaddress@intermas.com',
            'password': 'testpass123'
        })

        self.assertEqual(login_response.status_code, 200)
        self.assertContains(login_response, "Vous devez confirmer votre adresse e-mail pour vous connecter.")
        mock_send.assert_called_once()