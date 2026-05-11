#!/usr/bin/env python
"""
Test script to verify menu API behavior
"""
import os
import django
import json

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.base')
django.setup()

from rest_framework.test import APIRequestFactory
from menu.api.views import FoodTruckMenuView
from django.http import Http404

factory = APIRequestFactory()

# Try to get menu for 'cucina-di-pastaz'
request = factory.get('/api/foodtrucks/cucina-di-pastaz/menu/')
view = FoodTruckMenuView.as_view()

try:
    response = view(request, slug='cucina-di-pastaz')
    print(f"Response status: {response.status_code}")
    print(f"Response data: {json.dumps(response.data, indent=2, default=str)}")
except Http404 as e:
    print(f"404 Error: {e}")
except Exception as e:
    print(f"Error: {type(e).__name__}: {e}")
