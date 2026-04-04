# Internationalization (i18n) Setup

This directory contains translation files for the FoodTruck SaaS platform.

## Supported Languages

- English (en) - Default
- French (fr)
- Spanish (es)

## Creating Translations

### Extract translatable strings:
```bash
python manage.py makemessages -l fr
python manage.py makemessages -l es
```

### After translating .po files, compile:
```bash
python manage.py compilemessages
```

## Translation Strategy

We use a hybrid approach:
1. **Django i18n**: For UI strings and error messages
2. **API-Level Translation**: For model data (name, description fields)
3. **Accept-Language Header**: For automatic language negotiation in DRF

## Model Field Translation

Translatable fields on models:
- FoodTruck: name, description
- Menu: name
- Category: name
- Item: name, description
- OptionGroup: name
- Option: name
- Preference: name, description

These are handled via Content Negotiation in the API tier.

## Usage in Views/Serializers

```python
from django.utils.translation import gettext_lazy as _
from django.utils import translation

# Get current language
current_lang = translation.get_language()

# Use gettext_lazy for strings
title = _("My Title")
```

## Implementation Reference

See config/settings/base.py for i18n configuration.
