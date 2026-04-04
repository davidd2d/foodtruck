"""
Example DRF Serializers with Internationalization (i18n) Support

This module demonstrates how to implement language-aware serializers
that respect the Accept-Language header in API requests.
"""

from rest_framework import serializers
from django.utils.translation import gettext_lazy as _
from django.utils import translation
from config.utils import LanguageAwareSerializerMixin, get_requested_language

# Placeholder - import actual models when ready
# from foodtrucks.models import FoodTruck
# from menu.models import Menu, Item


class LanguageResponseMixin(serializers.Serializer):
    """
    Mixin that adds language metadata to any serializer response.
    
    Adds a 'language' field showing the current request language.
    """
    language = serializers.SerializerMethodField()
    
    def get_language(self, obj):
        """Return the language currently active in the request context."""
        request = self.context.get('request')
        if request:
            return get_requested_language(request)
        return translation.get_language()


# ============================================================================
# EXAMPLE 1: FoodTruck Serializer with Language Support
# ============================================================================

class FoodTruckExampleSerializer(LanguageAwareSerializerMixin, 
                                  LanguageResponseMixin,
                                  serializers.Serializer):
    """
    Example FoodTruck serializer demonstrating i18n.
    
    Features:
    - Automatically activates request language (via LanguageAwareSerializerMixin)
    - Includes current language in response (via LanguageResponseMixin)
    - UI strings like field labels are automatically translated
    
    Example Usage in View:
    
        def get_queryset(self):
            # Language is automatically activated by serializer mixin
            return FoodTruck.objects.all()
        
        def get_serializer(self, *args, **kwargs):
            return FoodTruckExampleSerializer(*args, **kwargs)
    """
    
    id = serializers.IntegerField()
    name = serializers.CharField(
        max_length=255,
        help_text=_("Name of the food truck")
    )
    description = serializers.CharField(
        allow_blank=True,
        help_text=_("Detailed description of the food truck")
    )
    phone = serializers.CharField(max_length=20)
    status = serializers.ChoiceField(choices=['active', 'inactive'])
    
    # This is added by LanguageResponseMixin
    # language = ...
    
    # Metadata field showing when this is in current user's language
    is_translated = serializers.SerializerMethodField()
    
    def get_is_translated(self, obj):
        """
        Indicates if data is available in the requested language.
        
        In full implementation, this would check translation availability.
        """
        request = self.context.get('request')
        if request:
            language = get_requested_language(request)
            # For now, always True (would check translation DB in production)
            return True
        return True
    
    class Meta:
        fields = ['id', 'name', 'description', 'phone', 'status', 'language', 'is_translated']


# ============================================================================
# EXAMPLE 2: Menu Item Serializer with Nested Translations
# ============================================================================

class MenuItemExampleSerializer(LanguageAwareSerializerMixin,
                                 LanguageResponseMixin,
                                 serializers.Serializer):
    """
    Menu item serializer with full i18n support.
    
    Demonstrates:
    - Translatable field handling
    - Nested serializer language awareness
    - Choice field translation
    
    Example Request:
        GET /api/menu-items/?category=appetizers
        Accept-Language: fr
        
    Example Response:
        {
            "id": 1,
            "name": "Salade César",  
            "description": "Laitue fraîche avec sauce César...",
            "price": "12.99",
            "language": "fr",
            "category": {
                "id": 1,
                "name": "Entrées"
            }
        }
    """
    
    id = serializers.IntegerField()
    name = serializers.CharField(
        max_length=255,
        help_text=_("Item name in the current language")
    )
    description = serializers.CharField(
        allow_blank=True,
        help_text=_("Item description")
    )
    price = serializers.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text=_("Price in USD")
    )
    available = serializers.BooleanField(
        default=True,
        help_text=_("Whether this item is currently available")
    )
    
    class Meta:
        fields = ['id', 'name', 'description', 'price', 'available', 'language']


# ============================================================================
# EXAMPLE 3: ViewSet Integration
# ============================================================================

class LanguageAwareViewSetExampleCode:
    """
    Code example showing how to integrate i18n into ViewSets.
    
    Copy this pattern into your actual views.py files.
    """
    
    EXAMPLE_CODE = """
    from rest_framework import viewsets
    from rest_framework.request import Request
    from config.utils import activate_request_language
    from .serializers import FoodTruckExampleSerializer
    
    
    class FoodTruckViewSet(viewsets.ModelViewSet):
        queryset = FoodTruck.objects.all()
        serializer_class = FoodTruckExampleSerializer
        
        def get_serializer_context(self):
            context = super().get_serializer_context()
            # Language is automatically handled by LanguageAwareSerializerMixin
            # But you can explicitly activate it here too:
            # activate_request_language(self.request)
            return context
        
        def list(self, request: Request, *args, **kwargs):
            # The request language is automatically activated
            # All serializer fields will be in the requested language
            return super().list(request, *args, **kwargs)
        
        def retrieve(self, request: Request, pk=None, *args, **kwargs):
            # Same applies to single object retrieval
            return super().retrieve(request, *args, **kwargs)
    """


# ============================================================================
# EXAMPLE 4: How to Handle Translations in Practice
# ============================================================================

class TranslationImplementationExamples:
    """
    Real examples of how translations work in the API.
    """
    
    @staticmethod
    def example_1_accept_language_header():
        """
        Example 1: Client respects Accept-Language header
        
        REQUEST:
            GET /api/foodtrucks/
            Accept-Language: fr
        
        PROCESSING:
            1. LocaleMiddleware (settings/base.py) detects 'fr'
            2. translation.activate('fr') is called
            3. All gettext_lazy(_('...')) strings are translated
            4. Serializer returns French translations
        
        RESPONSE:
            {
                "id": 1,
                "name": "Food Truck Excellent",
                "description": "Le meilleur camion à hot-dogs...",
                "language": "fr"
            }
        """
        pass
    
    @staticmethod
    def example_2_fallback_to_english():
        """
        Example 2: Unsupported language falls back to English
        
        REQUEST:
            GET /api/foodtrucks/
            Accept-Language: zh  (Chinese - not configured)
        
        PROCESSING:
            1. LocaleMiddleware detects 'zh'
            2. Not in settings.LANGUAGES, falls back to en
            3. All strings returned in English
        
        RESPONSE:
            {
                "id": 1,
                "name": "Food Truck Excellent",
                "description": "The best hot dog truck in town...",
                "language": "en"
            }
        """
        pass
    
    @staticmethod
    def example_3_no_language_preference():
        """
        Example 3: No Accept-Language header defaults to English
        
        REQUEST:
            GET /api/foodtrucks/
            (no Accept-Language header)
        
        PROCESSING:
            1. LocaleMiddleware finds no header
            2. Uses settings.LANGUAGE_CODE = 'en'
            3. Returns English response
        
        RESPONSE:
            {
                "id": 1,
                "name": "Food Truck Excellent",
                "description": "The best hot dog truck in town...",
                "language": "en"
            }
        """
        pass


# ============================================================================
# EXAMPLE 5: Manual Translation in Views
# ============================================================================

def example_translate_in_view():
    """
    Example of manually translating content in a view.
    
    This would go in your views.py or viewsets.py:
    """
    
    CODE = """
    from rest_framework.response import Response
    from django.utils import translation
    from config.utils import activate_request_language, get_requested_language
    
    
    class MyViewSet(viewsets.ViewSet):
        def list(self, request):
            # Activate the requested language
            language = activate_request_language(request)
            
            # Now all gettext_lazy strings are translated
            from django.utils.translation import gettext_lazy as _
            message = _("Food trucks loaded successfully")
            
            foodtrucks = FoodTruck.objects.all()
            serializer = FoodTruckExampleSerializer(
                foodtrucks,
                many=True,
                context={'request': request}  # Important!
            )
            
            return Response({
                'message': str(message),  # Converted to string with translation
                'language': language,
                'data': serializer.data
            })
    """
    return CODE


# ============================================================================
# EXAMPLE 6: Adding Translations to Your Models
# ============================================================================

class AddingTranslationsGuide:
    """
    Step-by-step guide to add translations to your project.
    """
    
    STEP_1_MARK_STRINGS = '''
    Step 1: Mark strings for translation in your models
    
    from django.utils.translation import gettext_lazy as _
    
    class FoodTruck(models.Model):
        """Mark field labels for translation."""
        name = models.CharField(
            max_length=255,
            help_text=_("Name of the food truck")  # Mark!
        )
        description = models.TextField(
            help_text=_("Description")  # Mark!
        )
        
        class Meta:
            verbose_name = _("Food Truck")  # Mark!
            verbose_name_plural = _("Food Trucks")  # Mark!
    '''
    
    STEP_2_EXTRACT = '''
    Step 2: Extract all marked strings to translation files
    
    # Terminal:
    python manage.py makemessages -l fr
    python manage.py makemessages -l es
    
    This creates:
    - locale/fr/LC_MESSAGES/django.po  (editable)
    - locale/es/LC_MESSAGES/django.po  (editable)
    '''
    
    STEP_3_TRANSLATE = '''
    Step 3: Edit .po files to add translations
    
    File: locale/fr/LC_MESSAGES/django.po
    
    #: foodtrucks/models.py
    msgid "Name of the food truck"
    msgstr "Nom du camion à hot-dogs"
    
    #: foodtrucks/models.py
    msgid "Description"
    msgstr "Description"
    
    #: foodtrucks/models.py
    msgid "Food Truck"
    msgstr "Camion à hot-dogs"
    '''
    
    STEP_4_COMPILE = '''
    Step 4: Compile translations to binary format
    
    # Terminal:
    python manage.py compilemessages
    
    This creates:
    - locale/fr/LC_MESSAGES/django.mo  (compiled)
    - locale/es/LC_MESSAGES/django.mo  (compiled)
    '''
    
    STEP_5_TEST = '''
    Step 5: Test your translations
    
    # Terminal:
    python manage.py runserver
    
    # Test with French
    curl -H "Accept-Language: fr" http://localhost:8000/api/foodtrucks/
    
    # Test with Spanish
    curl -H "Accept-Language: es" http://localhost:8000/api/foodtrucks/
    
    # Test with English (default)
    curl http://localhost:8000/api/foodtrucks/
    '''
