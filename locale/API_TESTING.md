"""
Internationalization API Testing Guide

This guide shows how to test language support in your API endpoints.
"""

# ============================================================================
# TEST 1: Using curl to Test Accept-Language Header
# ============================================================================

CURL_TESTS = """
# Test 1: Request with French language preference
curl -v \\
  -H "Accept-Language: fr" \\
  http://localhost:8000/api/foodtrucks/

# Test 2: Request with Spanish language preference
curl -v \\
  -H "Accept-Language: es" \\
  http://localhost:8000/api/foodtrucks/

# Test 3: Request with English (default)
curl -v \\
  http://localhost:8000/api/foodtrucks/

# Test 4: Request with language quality weights (French preferred, then English)
curl -v \\
  -H "Accept-Language: fr,en;q=0.9" \\
  http://localhost:8000/api/foodtrucks/

# Test 5: Test specific resource in French
curl -v \\
  -H "Accept-Language: fr" \\
  http://localhost:8000/api/foodtrucks/1/
"""


# ============================================================================
# TEST 2: Python Requests Library Testing
# ============================================================================

PYTHON_REQUESTS_TESTS = """
import requests

BASE_URL = "http://localhost:8000/api/foodtrucks/"

# Test 1: Request in French
response = requests.get(
    BASE_URL,
    headers={"Accept-Language": "fr"}
)
print(f"French Response: {response.json()}")
assert response.json()['language'] == 'fr'

# Test 2: Request in Spanish
response = requests.get(
    BASE_URL,
    headers={"Accept-Language": "es"}
)
print(f"Spanish Response: {response.json()}")
assert response.json()['language'] == 'es'

# Test 3: Request without language preference (English default)
response = requests.get(BASE_URL)
print(f"Default Response: {response.json()}")
assert response.json()['language'] == 'en'

# Test 4: Multiple language preferences with quality
response = requests.get(
    BASE_URL,
    headers={"Accept-Language": "fr,es;q=0.9,en;q=0.8"}
)
print(f"Weighted Preferences: {response.json()}")
assert response.json()['language'] == 'fr'  # Highest priority
"""


# ============================================================================
# TEST 3: Testing Specific Serializer Fields
# ============================================================================

SERIALIZER_FIELD_TESTS = """
import requests

BASE_URL = "http://localhost:8000/api/foodtrucks/1/"

# Test that 'name' field content matches language
response_fr = requests.get(
    BASE_URL,
    headers={"Accept-Language": "fr"}
).json()

response_es = requests.get(
    BASE_URL,
    headers={"Accept-Language": "es"}
).json()

response_en = requests.get(
    BASE_URL,
    headers={"Accept-Language": "en"}
).json()

print("French name:", response_fr['name'])
print("Spanish name:", response_es['name'])
print("English name:", response_en['name'])

# Verify all responses include language field
assert 'language' in response_fr
assert 'language' in response_es
assert 'language' in response_en
"""


# ============================================================================
# TEST 4: Testing Fallback Behavior
# ============================================================================

FALLBACK_TESTS = """
import requests

BASE_URL = "http://localhost:8000/api/foodtrucks/"

# Test 1: Unsupported language should fallback to English
response = requests.get(
    BASE_URL,
    headers={"Accept-Language": "zh"}  # Chinese (not configured)
)
print(f"Fallback language: {response.json()['language']}")
assert response.json()['language'] == 'en'  # Falls back to English

# Test 2: Partially supported language prefix
response = requests.get(
    BASE_URL,
    headers={"Accept-Language": "fr-CA"}  # French-Canadian, should use 'fr'
)
data = response.json()
# Should be 'fr' if the implementation handles language prefixes
print(f"French-Canadian -> {data['language']}")
"""


# ============================================================================
# TEST 5: Django Shell Testing
# ============================================================================

DJANGO_SHELL_TESTS = """
python manage.py shell

# Test 1: Verify language activation
from django.utils import translation
from django.utils.translation import gettext_lazy as _

translation.activate('fr')
print(translation.get_language())  # Should print 'fr'

# Test 2: Test gettext_lazy translation
message = _("Hello World")
print(message)  # Should print French translation if available

# Test 3: Test get_all_languages
print(translation.get_supported_languages_bidi())

# Test 4: Switch language
translation.activate('es')
print(translation.get_language())  # Should print 'es'

# Reset to English
translation.activate('en')
"""


# ============================================================================
# TEST 6: Django Test Client Testing
# ============================================================================

DJANGO_TEST_CLIENT_TESTS = """
from django.test import TestCase, Client
from django.urls import reverse

class I18nTestCase(TestCase):
    def setUp(self):
        self.client = Client()
    
    def test_french_request(self):
        response = self.client.get(
            '/api/foodtrucks/',
            HTTP_ACCEPT_LANGUAGE='fr'
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['language'], 'fr')
    
    def test_spanish_request(self):
        response = self.client.get(
            '/api/foodtrucks/',
            HTTP_ACCEPT_LANGUAGE='es'
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['language'], 'es')
    
    def test_default_language(self):
        # No Accept-Language header
        response = self.client.get('/api/foodtrucks/')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['language'], 'en')
    
    def test_unsupported_language_fallback(self):
        response = self.client.get(
            '/api/foodtrucks/',
            HTTP_ACCEPT_LANGUAGE='zh'  # Chinese (unsupported)
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        # Should fallback to English
        self.assertEqual(data['language'], 'en')
"""


# ============================================================================
# TEST 7: Swagger/OpenAPI Documentation Testing
# ============================================================================

SWAGGER_TESTING = """
# If using drf-spectacular for API documentation:

# Test endpoint with language parameter in docs
GET /api/schema/swagger-ui/

# Test individual endpoint with language variations:
GET /api/foodtrucks/
  ?Accept-Language=fr

# The Swagger UI will show:
- Accept-Language header field
- language field in response schema
- Example responses in different languages (if documented)

# Note: To document language support in Swagger, add to serializer:

from drf_spectacular.openapi import OpenApiParameter

class FoodTruckViewSet(viewsets.ModelViewSet):
    @extend_schema(parameters=[
        OpenApiParameter(
            name='Accept-Language',
            location=openapi.HEADER,
            description='Language preference (en, fr, es)',
            required=False,
        )
    ])
    def list(self, request):
        ...
"""


# ============================================================================
# TEST 8: Full Integration Test Example
# ============================================================================

FULL_INTEGRATION_TEST = """
# tests/test_i18n_integration.py

from django.test import TestCase, override_settings
from django.utils import translation
from rest_framework.test import APIClient
from foodtrucks.models import FoodTruck, Plan, Subscription
from users.models import User
import json

class I18nFullIntegrationTest(TestCase):
    \"\"\"Complete i18n functionality testing.\"\"\"
    
    def setUp(self):
        from django.utils.timezone import now, timedelta
        
        # Create test data
        self.user = User.objects.create_user(
            email='test@example.com',
            password='testpass123'
        )
        
        plan = Plan.objects.create(
            name='Free Plan',
            allows_ordering=True
        )
        
        Subscription.objects.create(
            user=self.user,
            plan=plan,
            status='active',
            expires_at=now() + timedelta(days=30)
        )
        
        self.food_truck = FoodTruck.objects.create(
            user=self.user,
            name='Joe\'s Hot Dogs',
            description='Best hot dogs in town'
        )
        
        self.client = APIClient()
        self.client.authenticate(user=self.user)
    
    def test_list_with_french_language(self):
        \"\"\"Test FoodTruck list endpoint with French language.\"\"\"
        response = self.client.get(
            '/api/foodtrucks/',
            HTTP_ACCEPT_LANGUAGE='fr'
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['language'], 'fr')
        # Check that content fields are present
        self.assertIn('results', data)
        self.assertEqual(len(data['results']), 1)
    
    def test_retrieve_with_spanish_language(self):
        \"\"\"Test FoodTruck detail endpoint with Spanish language.\"\"\"
        response = self.client.get(
            f'/api/foodtrucks/{self.food_truck.id}/',
            HTTP_ACCEPT_LANGUAGE='es'
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['language'], 'es')
        self.assertEqual(data['name'], self.food_truck.name)
    
    def test_language_fallback(self):
        \"\"\"Test that unsupported language falls back to English.\"\"\"
        response = self.client.get(
            '/api/foodtrucks/',
            HTTP_ACCEPT_LANGUAGE='ja'  # Japanese (unsupported)
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['language'], 'en')
    
    def test_language_from_different_clients(self):
        \"\"\"Test multiple clients with different language preferences.\"\"\"
        client_fr = APIClient()
        client_es = APIClient()
        client_en = APIClient()
        
        client_fr.authenticate(user=self.user)
        client_es.authenticate(user=self.user)
        client_en.authenticate(user=self.user)
        
        # Test French
        response_fr = client_fr.get(
            '/api/foodtrucks/',
            HTTP_ACCEPT_LANGUAGE='fr'
        )
        self.assertEqual(response_fr.json()['language'], 'fr')
        
        # Test Spanish
        response_es = client_es.get(
            '/api/foodtrucks/',
            HTTP_ACCEPT_LANGUAGE='es'
        )
        self.assertEqual(response_es.json()['language'], 'es')
        
        # Test English
        response_en = client_en.get(
            '/api/foodtrucks/',
            HTTP_ACCEPT_LANGUAGE='en'
        )
        self.assertEqual(response_en.json()['language'], 'en')
"""


# ============================================================================
# TEST 9: Performance Testing With Language Activation
# ============================================================================

PERFORMANCE_TESTING = """
import time
from django.test import Client
from django.utils import translation

client = Client()

# Test response time for different languages
languages = ['en', 'fr', 'es']

for lang in languages:
    start = time.time()
    
    for _ in range(100):  # 100 requests per language
        response = client.get(
            '/api/foodtrucks/',
            HTTP_ACCEPT_LANGUAGE=lang
        )
    
    elapsed = time.time() - start
    print(f"Language: {lang}, Time: {elapsed:.2f}s, Avg: {elapsed/100:.4f}s")

# Note: Language activation should be minimal overhead
# Most time will be database queries, not translation
"""


# ============================================================================
# TEST 10: Testing with Browser DevTools
# ============================================================================

BROWSER_TESTING = """
# Open your API in Firefox/Chrome/Safari following these steps:

## Step 1: Open API endpoint
http://localhost:8000/api/foodtrucks/

## Step 2: Verify Accept-Language header is sent
1. Open DevTools (F12)
2. Go to Network tab
3. Refresh page
4. Click on the request
5. Look for "Accept-Language: en-US,en;q=0.9" (or similar)

## Step 3: Change language and test
1. Chrome: 
   - Settings → Languages → Change language
   - Clear cache
   - Refresh page
   - Check Accept-Language header changes

2. Firefox:
   - about:config
   - intl.accept_languages = "fr"
   - Refresh page
   - Check Accept-Language header is now "fr"

## Step 4: Test with curl for precise control
curl -H "Accept-Language: fr" http://localhost:8000/api/foodtrucks/
curl -H "Accept-Language: es" http://localhost:8000/api/foodtrucks/
"""


# ============================================================================
# EXPECTED TEST RESULTS
# ============================================================================

EXPECTED_RESULTS = """
All tests should show:

1. ✅ French requests (Accept-Language: fr) return response with language: "fr"
2. ✅ Spanish requests (Accept-Language: es) return response with language: "es"
3. ✅ English requests return response with language: "en"
4. ✅ Unsupported languages fallback to "en"
5. ✅ No Accept-Language header defaults to "en"
6. ✅ All serializer fields are present and valid
7. ✅ Requests complete within acceptable time (no translation overhead)
8. ✅ Django middleware properly activates language context
9. ✅ Error messages respect language preference
10. ✅ Admin interface shows language selector
"""
