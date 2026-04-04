"""
Internationalization utilities for API views and serializers.

Provides language detection and content negotiation helpers for DRF.
"""

from django.utils import translation
from django.conf import settings
from rest_framework.request import Request


def get_requested_language(request: Request) -> str:
    """
    Get the language requested by the client via Accept-Language header.
    
    Args:
        request: DRF request object
        
    Returns:
        Language code ('en', 'fr', 'es', or default)
        
    Example:
        >>> request.META.get('HTTP_ACCEPT_LANGUAGE', '')
        'fr,fr-FR;q=0.9,en;q=0.8'
        >>> get_requested_language(request)
        'fr'
    """
    # Get Accept-Language header
    accept_language = request.META.get('HTTP_ACCEPT_LANGUAGE', '')
    
    if not accept_language:
        return settings.LANGUAGE_CODE
    
    # Parse Accept-Language header (simple implementation)
    # Format: "fr,fr-FR;q=0.9,en;q=0.8"
    # We take the first language code (highest priority)
    languages = accept_language.split(',')
    if languages:
        first_choice = languages[0].strip()
        # Extract just the language code (e.g., 'fr' from 'fr-FR')
        language_code = first_choice.split('-')[0].split(';')[0].strip()
        
        # Validate against configured languages
        valid_languages = [code for code, _ in settings.LANGUAGES]
        if language_code in valid_languages:
            return language_code
    
    return settings.LANGUAGE_CODE


def activate_request_language(request: Request) -> str:
    """
    Activate the language for this request based on Accept-Language header.
    
    This should be called in a view or serializer to set the translation context.
    
    Args:
        request: DRF request object
        
    Returns:
        The activated language code
        
    Example:
        def get(self, request):
            language = activate_request_language(request)
            # Now all gettext_lazy strings will be in this language
    """
    language = get_requested_language(request)
    translation.activate(language)
    return language


class LanguageAwareSerializerMixin:
    """
    Mixin for DRF serializers to automatically activate request language.
    
    Usage:
        class MySerializer(LanguageAwareSerializerMixin, serializers.ModelSerializer):
            class Meta:
                model = MyModel
                fields = ['name', 'description']
    
    The mixin will:
    1. Automatically activate the language from Accept-Language header
    2. Add 'language' field to serializer showing current language
    """
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Activate language if request is in context
        request = self.context.get('request')
        if request:
            activate_request_language(request)
    
    def to_representation(self, instance):
        """Ensure language context is active during serialization."""
        request = self.context.get('request')
        if request:
            with translation.override(get_requested_language(request)):
                return super().to_representation(instance)
        return super().to_representation(instance)


def get_language_from_context(context: dict) -> str:
    """
    Extract and validate language from serializer context.
    
    Args:
        context: Serializer context dict
        
    Returns:
        Language code or default
    """
    request = context.get('request')
    if request:
        return get_requested_language(request)
    return settings.LANGUAGE_CODE


# Translation cache for model field translations
# In production, use cache framework (Redis) or database lookups
TRANSLATION_CACHE = {
    'fr': {
        'burger': 'Hamburger',
        'pizza': 'Pizza',
        'sushi': 'Sushi',
    },
    'es': {
        'burger': 'Hamburguesa',
        'pizza': 'Pizza',
        'sushi': 'Sushi',
    },
}


def translate_choice(value: str, language_code: str) -> str:
    """
    Translate a choice/enum value to the given language.
    
    Args:
        value: Original value/key
        language_code: Target language ('fr', 'es', etc.)
        
    Returns:
        Translated value or original if not found
        
    Example:
        >>> translate_choice('burger', 'fr')
        'Hamburger'
    """
    if language_code in TRANSLATION_CACHE:
        return TRANSLATION_CACHE[language_code].get(value, value)
    return value


def translate_field(instance, field_name: str, language_code: str) -> str:
    """
    Get translated field value for model instance.
    
    This is a placeholder for future full translation implementation.
    Currently returns the original value.
    
    Args:
        instance: Model instance
        field_name: Field to translate
        language_code: Target language
        
    Returns:
        Original or translated value
        
    Example:
        >>> food_truck = FoodTruck.objects.get(id=1)
        >>> translate_field(food_truck, 'name', 'fr')
        'Camion à hot-dogs' (if available)
    """
    # For now, returns original value
    # In Phase 2, this would look up translations from django-modeltranslation
    # or a custom translation table
    return getattr(instance, field_name, None)
