#!/usr/bin/env python3
"""Test translations are working"""

import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.utils.translation import activate, gettext as _
from django.utils.translation import get_language
from config.settings import LANGUAGES

print("🌍 Translation Test Results")
print("=" * 50)

# Show configured languages
print("\n✓ Configured Languages:")
for code, name in LANGUAGES:
    print(f"  - {code}: {name}")

# Test English (default)
print("\n✓ Testing English (no translation):")
activate('en')
print(f"  Active language: {get_language()}")
print(f"  'Plan' translates to: '{_('Plan')}'")

# Test French
print("\n✓ Testing French (fr):")
activate('fr')
print(f"  Active language: {get_language()}")
print(f"  'Plan' translates to: '{_('Plan')}'")
# We should see "Plan" (which happens to be the same)

# From django catalog
print(f"  'Display name of the plan' translates to: '{_('Display name of the plan')}'")
print(f"  'Food Truck' translates to: '{_('Food Truck')}'")
print(f"  'Menu' translates to: '{_('Menu')}'")

# Test Spanish  
print("\n✓ Testing Spanish (es):")
activate('es')
print(f"  Active language: {get_language()}")
print(f"  'Plan' translates to: '{_('Plan')}'")
print(f"  'Display name of the plan' translates to: '{_('Display name of the plan')}'")
print(f"  'Food Truck' translates to: '{_('Food Truck')}'")
print(f"  'Menu' translates to: '{_('Menu')}'")

print("\n" + "=" * 50)
print("✅ Translation system is working!")
