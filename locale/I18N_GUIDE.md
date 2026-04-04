# Internationalization (i18n) Implementation Guide

## Overview

This Django SaaS application implements comprehensive internationalization support with:
- **English** (en) - Default language
- **French** (fr)
- **Spanish** (es)

## Architecture

We use a **hybrid i18n approach**:

1. **Django i18n system**: For UI strings, error messages, and admin interface
2. **API-Level Language Handling**: For model data (names, descriptions)
3. **Content Negotiation**: Via `Accept-Language` header in API requests

This approach is more appropriate for DRF-based APIs and avoids complex model translation libraries.

---

## Part 1: Django i18n Setup ✅

### Configuration (settings/base.py)

```python
LANGUAGE_CODE = "en"

LANGUAGES = [
    ("en", "English"),
    ("fr", "French"),
    ("es", "Spanish"),
]

USE_I18N = True
LOCALE_PATHS = [
    BASE_DIR / 'locale',
]

# Middleware for automatic language detection
MIDDLEWARE = [
    ...
    'django.middleware.locale.LocaleMiddleware',
    ...
]
```

### Key Features
- **LocaleMiddleware**: Automatically sets language based on `Accept-Language` header
- **LOCALE_PATHS**: Django looks for translation files in `locale/` directory
- **USE_I18N**: Enables all i18n features

---

## Part 2: Working with Translations

### Command 1: Extract Translatable Strings

```bash
# Extract all strings marked with gettext_lazy() or _()
python manage.py makemessages -l fr
python manage.py makemessages -l es

# This creates:
# locale/fr/LC_MESSAGES/django.po
# locale/es/LC_MESSAGES/django.po
```

The `.po` files contain all translatable strings for manual translation.

### Command 2: Compile Translations

After translating the `.po` files:

```bash
# Compile translations to binary format
python manage.py compilemessages

# Creates:
# locale/fr/LC_MESSAGES/django.mo
# locale/es/LC_MESSAGES/django.mo
```

---

## Part 3: Mark Strings for Translation

### In Python Code

```python
from django.utils.translation import gettext_lazy as _

# For constants/module-level strings (use gettext_lazy)
error_message = _("User not found")
page_title = _("Welcome to our platform")

# For runtime strings (use gettext)
from django.utils.translation import gettext as _
message = _("Hello, {}").format(user_name)
```

### In Views

```python
from django.shortcuts import render
from django.utils.translation import gettext_lazy as _

def my_view(request):
    context = {
        'title': _('My Page Title'),
        'messages': [_('Message 1'), _('Message 2')],
    }
    return render(request, 'template.html', context)
```

### In Admin

```python
from django.contrib import admin
from django.utils.translation import gettext_lazy as _

class MyModelAdmin(admin.ModelAdmin):
    list_display = (_('Name'), _('Email'))
```

---

## Part 4: API Language Support

### Getting Current Language in Serializers

```python
from rest_framework import serializers
from django.utils import translation

class FoodTruckSerializer(serializers.ModelSerializer):
    language = serializers.SerializerMethodField()
    
    def get_language(self, obj):
        """Return current request language."""
        return translation.get_language()
    
    class Meta:
        model = FoodTruck
        fields = ['id', 'name', 'description', 'language']
```

### Content Negotiation with Accept-Language Header

```python
# Client request with language preference:
GET /api/foodtrucks/
Headers: Accept-Language: fr

# The LocaleMiddleware automatically sets the language context
# All gettext_lazy() strings will be translated to French
```

### Handling Model Data Translations

For fields like `name` and `description`, we recommend:

1. **Option A: Store in separate language tables (future)**
   ```python
   # If full model translation needed, use django-modeltranslation
   # which handles this elegantly
   ```

2. **Option B: Handle in DTOs/Serializers**
   ```python
   class FoodTruckTranslator:
       """Translate model fields based on language context."""
       
       @staticmethod
       def translate_field(obj, field_name, language):
           # Lookup translated content from cache/DB
           # Return translated version or fallback to default
           return getattr(obj, field_name)  # For now, returns as-is
   ```

3. **Option C: Use translation files for enums/choices**
   ```python
   from django.utils.translation import gettext_lazy as _
   
   FOOD_TYPES = [
       ('burger', _('Burger')),
       ('pizza', _('Pizza')),
       ('sushi', _('Sushi')),
   ]
   ```

---

## Part 5: Language Fallback Strategy

### Current Behavior

1. **Request**: Client sends `Accept-Language: fr`
2. **Middleware**: Sets `django.utils.translation.get_language() = 'fr'`
3. **Translation**: Django looks for French translations in `locale/fr/LC_MESSAGES/django.mo`
4. **Fallback**: If not found, falls back to English (LANGUAGE_CODE='en')

### Configuration for Fallback

```python
# settings/base.py
LANGUAGE_CODE = 'en'  # Default fallback language

LANGUAGES = [
    ('en', 'English'),
    ('fr', 'French'),
    ('es', 'Spanish'),
]
```

---

## Part 6: Admin Interface Translation

The Django admin automatically supports language selection:
1. User clicks language selector in admin
2. Admin interface translates to selected language
3. All ModelAdmin fields using `_()` are translated

```python
@admin.register(MyModel)
class MyModelAdmin(admin.ModelAdmin):
    list_display = (_('Name'), _('Created'))
    search_fields = (_('Description'),)
```

---

## Next Steps: Full Model Translation

For production, consider upgrading with **django-modeltranslation**:

```bash
pip install django-modeltranslation
```

This allows storing and querying translations per language:

```python
from modeltranslation.translator import register, TranslationOptions
from .models import FoodTruck

@register(FoodTruck)
class FoodTruckTranslationOptions(TranslationOptions):
    fields = ('name', 'description')
```

Then query as:

```python
# Automatically uses current language
truck = FoodTruck.objects.get(id=1)
print(truck.name)  # Returns French, Spansih, or English based on settings.LANGUAGE_CODE
```

---

## Testing Translations

### Manual Testing

```bash
# Start server
python manage.py runserver

# Test English (default)
curl -H "Accept-Language: en" http://localhost:8000/api/foodtrucks/

# Test French
curl -H "Accept-Language: fr" http://localhost:8000/api/foodtrucks/

# Test Spanish
curl -H "Accept-Language: es" http://localhost:8000/api/foodtrucks/
```

### Django Shell Testing

```python
python manage.py shell

from django.utils import translation
from django.utils.translation import gettext_lazy as _

# Test language switching
translation.activate('fr')
print(translation.get_language())  # 'fr'

message = _('Hello World')
print(message)  # Prints French translation if available

# Switch back
translation.activate('en')
```

---

## Summary

| Component | Status | Implementation |
|-----------|--------|-----------------|
| Settings | ✅ Complete | LANGUAGE_CODE, LANGUAGES, LOCALE_PATHS configured |
| Middleware | ✅ Complete | LocaleMiddleware added for auto-detection |
| String Marking | ⚠️ In Progress | Use gettext_lazy as _ for all user-visible strings |
| Translations | ⏳ To Do | Run makemessages, translate .po files, compilemessages |
| Model Data | 🔄 Optional | Can upgrade to django-modeltranslation in Phase 2 |
| API Support | ✅ Complete | Accept-Language header fully supported |

---

## Files Structure

```
locale/
├── README.md                          # This file
├── fr/
│   └── LC_MESSAGES/
│       ├── django.po                  # French translations (editable)
│       └── django.mo                  # Compiled French translations
├── es/
│   └── LC_MESSAGES/
│       ├── django.po                  # Spanish translations (editable)
│       └── django.mo                  # Compiled Spanish translations
```

---

## Reference Commands

```bash
# Extract messages
python manage.py makemessages -l fr
python manage.py makemessages -l es

# Compile messages
python manage.py compilemessages

# Check translation file syntax
python manage.py compilemessages --check

# View all languages
python manage.py showmigrations --no-migrate
```

---

For questions or to implement full model translations, refer to:
- Django i18n Docs: https://docs.djangoproject.com/en/4.2/topics/i18n/
- django-modeltranslation: https://django-modeltranslation.readthedocs.io/
