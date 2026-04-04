# accounts/tests/fixtures.py

import pytest
from django.test import TestCase
from foodtrucks.tests.factories import UserFactory


class AccountsTestFixtures(TestCase):
    """Base class with common test fixtures for accounts tests."""

    def setUp(self):
        self.user = UserFactory()
        self.other_user = UserFactory()
        self.superuser = UserFactory(is_superuser=True, is_staff=True)