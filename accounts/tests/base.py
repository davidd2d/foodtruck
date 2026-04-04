"""
Base test classes for JWT authentication in API tests.
"""
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import AccessToken


class JWTAPITestCase(APITestCase):
    """
    Base test case for API tests that require JWT authentication.
    
    Provides helper methods to authenticate users via JWT tokens.
    """

    def get_token_for_user(self, user):
        """
        Generate a JWT access token for a given user.
        
        Args:
            user: The user to generate a token for
            
        Returns:
            str: JWT access token
        """
        return str(AccessToken.for_user(user))

    def authenticate_user(self, user):
        """
        Authenticate the test client with a JWT token for the given user.
        
        Args:
            user: The user to authenticate as
        """
        token = self.get_token_for_user(user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')

    def unauthenticate(self):
        """Remove authentication from the test client."""
        self.client.credentials()
