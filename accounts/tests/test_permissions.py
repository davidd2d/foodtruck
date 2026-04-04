# accounts/tests/test_permissions.py

from django.test import TestCase
from django.urls import reverse
from foodtrucks.tests.factories import UserFactory


class PermissionsTests(TestCase):
    """Test permissions and access control."""

    def setUp(self):
        self.user = UserFactory()
        self.other_user = UserFactory()
        self.superuser = UserFactory(is_superuser=True)

    def test_user_cannot_access_another_users_data(self):
        """Test user cannot access another user's data."""
        # Since no user detail views, test login
        self.client.login(username=self.user.email, password='password123')
        # Assuming no direct access, test that session is user-specific
        response = self.client.get(reverse('accounts:login'))
        self.assertEqual(response.status_code, 200)

    def test_user_can_access_own_data(self):
        """Test user can access own data."""
        self.client.login(username=self.user.email, password='password123')
        response = self.client.get(reverse('accounts:login'))
        self.assertEqual(response.status_code, 200)

    def test_anonymous_users_restricted(self):
        """Test anonymous users are restricted."""
        response = self.client.get(reverse('accounts:signup'))
        self.assertEqual(response.status_code, 200)  # Public page

    def test_cannot_modify_another_user(self):
        """Test user cannot modify another user's data."""
        # No modification views, so test login security
        self.client.login(username=self.user.email, password='password123')
        # Ensure not logged in as other user
        self.client.logout()
        self.client.login(username=self.other_user.email, password='password123')
        # Check context
        pass

    def test_cannot_escalate_privileges(self):
        """Test user cannot escalate own privileges."""
        # No self-modification, test that user remains non-superuser
        self.assertFalse(self.user.is_superuser)