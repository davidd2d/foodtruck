import json
import logging
import mimetypes
import os
import base64
import re
from decimal import Decimal, InvalidOperation
from typing import Dict, List, Any, Optional, Tuple
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.files.storage import default_storage
from django.db import transaction
from config.services.openai_client import OpenAIService
from onboarding.models import OnboardingImport
from foodtrucks.models import FoodTruck
from menu.models import Menu, Category, Item, OptionGroup, Option
from preferences.models import Preference

logger = logging.getLogger(__name__)


class AIOnboardingService:
    """Service for AI-powered onboarding data processing and entity creation."""

    LANGUAGE_NAMES = {
        'en': 'English',
        'fr': 'French',
        'es': 'Spanish',
    }

    COLOR_NAME_TO_HEX = {
        'red': '#FF0000',
        'dark red': '#8B0000',
        'light red': '#FF7F7F',
        'beige': '#F5F5DC',
        'black': '#000000',
        'white': '#FFFFFF',
        'navy': '#000080',
        'blue': '#0000FF',
        'green': '#008000',
        'olive': '#808000',
        'yellow': '#FFFF00',
        'orange': '#FFA500',
        'purple': '#800080',
        'brown': '#654321',
        'gray': '#808080',
        'grey': '#808080',
        'pink': '#FFC0CB',
        'teal': '#008080',
    }
    HEX_COLOR_RE = re.compile(r'^#[0-9A-Fa-f]{6}$')
    DEFAULT_PRIMARY_COLOR = '#000000'
    DEFAULT_SECONDARY_COLOR = '#FFFFFF'

    def __init__(self):
        self.openai_service = OpenAIService()

    def _normalize_language_code(self, language_code: Optional[str]) -> str:
        """Normalize a language code to the configured choices."""
        valid_codes = {code for code, _ in settings.LANGUAGES}
        if language_code in valid_codes:
            return language_code
        return settings.LANGUAGE_CODE

    def _get_language_name(self, language_code: str) -> str:
        """Return a display name for prompt instructions."""
        return self.LANGUAGE_NAMES.get(language_code, self.LANGUAGE_NAMES[settings.LANGUAGE_CODE])

    def process_import(self, import_id: int) -> Dict[str, Any]:
        """
        Main method to process an onboarding import.

        Steps:
        1. Clean input text
        2. Call OpenAI for text extraction
        3. Call OpenAI for image analysis if images exist
        4. Merge results
        5. Normalize data
        6. Save structured JSON into parsed_data

        Args:
            import_id: ID of the OnboardingImport instance

        Returns:
            Dict containing processing result with status and data
        """
        try:
            import_instance = OnboardingImport.objects.get(id=import_id)
            import_instance.status = 'processing'
            import_instance.save()

            # Step 1: Clean input text
            cleaned_text = self._clean_input_text(import_instance.raw_text)

            # Step 2: Call OpenAI for text extraction
            text_data = self._extract_from_text(cleaned_text)

            # Step 3: Call OpenAI for image analysis if images exist
            menu_images = import_instance.image_files.filter(image_type__in=['menu', 'other'])
            logo_images = import_instance.image_files.filter(image_type='logo')
            image_data, logo_data = self.analyze_images(menu_images, logo_images)

            # Step 4: Merge results
            merged_data = self._merge_data(text_data, image_data, logo_data)

            # Step 5: Normalize data
            normalized_data = self._normalize_data(merged_data)

            # Step 6: Save structured JSON
            import_instance.parsed_data = normalized_data
            import_instance.status = 'completed'
            import_instance.save()

            return {
                'status': 'success',
                'data': normalized_data,
                'import_id': import_id
            }

        except Exception as e:
            logger.error(f"Error processing import {import_id}: {str(e)}")
            import_instance.status = 'failed'
            import_instance.save()
            return {
                'status': 'error',
                'error': str(e),
                'import_id': import_id
            }

    def _clean_input_text(self, raw_text: str) -> str:
        """Clean and normalize input text."""
        if not raw_text:
            return ""

        # Basic cleaning: remove extra whitespace, normalize line breaks
        cleaned = raw_text.strip()
        cleaned = ' '.join(cleaned.split())  # Normalize whitespace
        return cleaned

    def _extract_from_text(self, text: str) -> Dict[str, Any]:
        """Extract structured data from text using OpenAI."""
        if not text:
            return self._get_empty_structure()

        prompt = self._build_text_extraction_prompt(text)

        try:
            response = self.openai_service.generate(
                prompt=prompt,
                model="gpt-4o",  # Use GPT-4o for consistency
                max_tokens=2000
            )

            # Clean the response - sometimes OpenAI returns markdown code blocks
            cleaned_response = response.strip()
            if cleaned_response.startswith('```json'):
                cleaned_response = cleaned_response[7:]
            if cleaned_response.endswith('```'):
                cleaned_response = cleaned_response[:-3]
            cleaned_response = cleaned_response.strip()

            # Parse JSON response
            data = json.loads(cleaned_response)
            return data

        except (json.JSONDecodeError, ValueError) as e:
            logger.warning(f"Failed to parse OpenAI response: {e}")
            logger.warning(f"Raw response was: {response}")
            return self._get_empty_structure()

    def analyze_images(self, menu_images, logo_images):
        """Analyze menu and logo images separately."""
        menu_paths = [img.image.path for img in menu_images if img.image]
        logo_paths = [img.image.path for img in logo_images if img.image]

        return self._analyze_menu_images(menu_paths), self._analyze_logo_images(logo_paths)

    def _analyze_menu_images(self, images: List[str]) -> Dict[str, Any]:
        """Analyze menu images using OpenAI Vision and extract structured menu data."""
        if not images:
            return {}

        logger.info("Analyzing %d menu images for pricing/data", len(images))
        image_inputs = self._build_image_inputs(images)

        if not image_inputs:
            logger.warning("No valid menu image references available")
            return {}

        try:
            response = self.openai_service.generate_with_images(
                prompt=self._build_menu_image_prompt(),
                image_inputs=image_inputs,
                model="gpt-4o",
                max_tokens=1800
            )

            logger.info("Menu image analysis raw response: %r", response)
            data = self._parse_image_response(response)
            return data
        except Exception as e:
            logger.error("Menu image analysis failed: %s", e)
            return {}

    def _analyze_logo_images(self, images: List[str]) -> Dict[str, Any]:
        """Extract branding colors from logo images."""
        if not images:
            return {}

        logger.info("Analyzing %d logo images for branding colors", len(images))
        image_inputs = self._build_image_inputs(images)

        if not image_inputs:
            logger.warning("No valid logo image references available")
            return {}

        try:
            response = self.openai_service.generate_with_images(
                prompt=self._build_logo_analysis_prompt(),
                image_inputs=image_inputs,
                model="gpt-4o",
                max_tokens=600
            )

            logger.info("Logo analysis raw response: %r", response)
            data = self._parse_image_response(response)
            return {'branding': data} if data else {}
        except Exception as e:
            logger.error("Logo analysis failed: %s", e)
            return {}

    def _build_image_inputs(self, image_paths: List[str]) -> List[Dict[str, Any]]:
        """Prepare OpenAI-compatible references for uploaded files."""
        image_inputs = []
        for image_path in image_paths:
            input_reference = self._build_image_input_reference(image_path)
            if input_reference:
                image_inputs.append(input_reference)
        return image_inputs

    def _parse_image_response(self, response: str) -> Dict[str, Any]:
        """Parse and clean OpenAI's image analysis response."""
        if not response or not response.strip():
            return {}

        cleaned_response = response.strip()
        if cleaned_response.startswith('```json'):
            cleaned_response = cleaned_response[7:]
        if cleaned_response.endswith('```'):
            cleaned_response = cleaned_response[:-3]
        cleaned_response = cleaned_response.strip()

        try:
            data = json.loads(cleaned_response)
            if isinstance(data, dict):
                return data
        except (json.JSONDecodeError, ValueError) as exc:
            logger.warning("Failed to parse image response: %s", exc)
            logger.warning("Raw response: %r", response)

        return {}

    def _build_image_input_reference(self, image_path: str) -> Optional[Dict[str, Any]]:
        """Create an OpenAI-compatible image input reference from a path or URL."""
        if not image_path:
            return None

        # Validate file exists
        if not os.path.exists(image_path):
            logger.warning("Image file does not exist: %s", image_path)
            return None

        try:
            # Encode image to base64
            base64_data = self._encode_image_to_base64(image_path)
            mime_type = mimetypes.guess_type(image_path)[0] or 'image/jpeg'

            return {
                "type": "image_url",
                "image_url": {
                    "url": f"data:{mime_type};base64,{base64_data}"
                }
            }
        except Exception as exc:
            logger.warning("Failed to prepare image reference for %s: %s", image_path, exc)
            return None

    def _encode_image_to_base64(self, image_path: str) -> str:
        """Encode an image file to base64 string."""
        with open(image_path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode('utf-8')

    def _merge_data(self, text_data: Dict, image_data: Dict, logo_data: Dict = None) -> Dict:
        """Merge text and image analysis results with priority rules."""
        merged = self._get_empty_structure()

        merged['foodtruck'].update(text_data.get('foodtruck', {}))
        merged['branding'].update(text_data.get('branding', {}))
        merged['menu'] = [
            {
                'category': self._normalize_category(category.get('category')),
                'items': category.get('items', []) or []
            }
            for category in text_data.get('menu', [])
        ]

        for key, value in image_data.get('foodtruck', {}).items():
            if value and not merged['foodtruck'].get(key):
                merged['foodtruck'][key] = value

        for img_category in image_data.get('menu', []):
            category_name = self._normalize_category(img_category.get('category'))
            existing_category = next(
                (cat for cat in merged['menu'] if cat.get('category', '').lower() == category_name.lower()),
                None
            )

            if not existing_category:
                existing_category = {
                    'category': category_name,
                    'items': []
                }
                merged['menu'].append(existing_category)

            for img_item in img_category.get('items', []):
                img_name = self._normalize_item_name(img_item.get('name'))
                if not img_name:
                    continue

                existing_item = next(
                    (item for item in existing_category['items']
                     if self._normalize_item_name(item.get('name')) == img_name),
                    None
                )

                if existing_item:
                    if img_item.get('price') is not None:
                        existing_item['price'] = img_item.get('price')
                        if img_item.get('currency'):
                            existing_item['currency'] = img_item.get('currency')
                        if not existing_item.get('description') and img_item.get('description'):
                            existing_item['description'] = img_item.get('description')
                else:
                    existing_category['items'].append({
                        'name': img_item.get('name', '').strip(),
                        'description': img_item.get('description', '') or '',
                        'price': img_item.get('price'),
                        'currency': img_item.get('currency', '') or '',
                        'options': img_item.get('options', []) or []
                    })

        for key, value in image_data.get('branding', {}).items():
            if value and not merged['branding'].get(key):
                merged['branding'][key] = value

        if logo_data:
            for key, value in logo_data.get('branding', {}).items():
                if value:
                    merged['branding'][key] = value

        return merged

    def _normalize_data(self, data: Dict) -> Dict:
        """Normalize and clean the extracted data."""
        normalized = self._get_empty_structure()
        normalized['foodtruck'].update(data.get('foodtruck', {}))
        normalized['branding'] = self.normalize_colors(data.get('branding', {}))
        normalized['menu'] = data.get('menu', []) or []

        if 'foodtruck' in normalized and 'preferences' in normalized['foodtruck']:
            normalized['foodtruck']['preferences'] = self._normalize_preferences(
                normalized['foodtruck']['preferences']
            )

        for category in normalized['menu']:
            category['category'] = self._normalize_category(category.get('category'))
            items = []
            seen = set()

            for item in category.get('items', []) or []:
                name = item.get('name', '')
                normalized_name = self._normalize_item_name(name)
                if not normalized_name:
                    continue

                raw_currency = item.get('currency') or self._detect_currency(str(item.get('price', '') or ''))
                currency = self._normalize_currency(raw_currency)
                price, corrected = self._normalize_price(item.get('price'))
                description = (item.get('description') or '').strip()
                options = item.get('options', []) or []

                normalized_item = {
                    'name': name.strip(),
                    'description': description,
                    'price': float(price) if price is not None else None,
                    'currency': currency,
                    'options': options,
                    'corrected': corrected
                }

                item_key = (normalized_name, normalized_item['price'], currency)
                if item_key in seen:
                    continue

                seen.add(item_key)
                items.append(normalized_item)

            category['items'] = items

        return normalized

    def normalize_colors(self, branding_data: Dict[str, Any]) -> Dict[str, Optional[str]]:
        """Normalize branding colors into HEX strings ready for the frontend."""
        normalized = {
            'primary_color': self._resolve_color_value(branding_data.get('primary_color')) or self.DEFAULT_PRIMARY_COLOR,
            'secondary_color': self._resolve_color_value(branding_data.get('secondary_color')) or self.DEFAULT_SECONDARY_COLOR,
            'style': branding_data.get('style', '')
        }
        return normalized

    def _resolve_color_value(self, raw_value: Any) -> Optional[str]:
        """Resolve various color representations into a validated HEX string."""
        name = None
        hex_candidate = None

        if isinstance(raw_value, dict):
            hex_candidate = raw_value.get('hex') or raw_value.get('HEX')
            name = raw_value.get('name')
        else:
            if isinstance(raw_value, str):
                hex_candidate = raw_value
                name = raw_value

        if isinstance(hex_candidate, str) and hex_candidate.strip():
            if not hex_candidate.startswith('#') and len(hex_candidate.strip()) == 6:
                hex_candidate = f"#{hex_candidate.strip()}"
            if self.HEX_COLOR_RE.match(hex_candidate):
                return self._normalize_hex(hex_candidate)

        if name:
            mapped = self.COLOR_NAME_TO_HEX.get(name.strip().lower())
            if mapped:
                return mapped

        return None

    def _normalize_hex(self, value: str) -> str:
        """Normalize hex representation to upper-case with leading #."""
        normalized = value.strip().upper()
        if not normalized.startswith('#'):
            normalized = f'#{normalized}'
        return normalized

    def _normalize_preferences(self, preferences: List[str]) -> List[str]:
        """Map text preferences to existing Preference objects."""
        if not preferences:
            return []

        normalized = []
        existing_prefs = {}
        for pref in Preference.objects.all():
            # Create multiple variations
            existing_prefs[pref.name.lower()] = pref.name
            existing_prefs[pref.name.lower().replace(' ', '-')] = pref.name
            existing_prefs[pref.name.lower().replace('-', ' ')] = pref.name

        for pref in preferences:
            pref_lower = pref.lower().strip()
            if pref_lower in existing_prefs:
                normalized.append(existing_prefs[pref_lower])
            else:
                # Keep original if no match found
                normalized.append(pref.strip())

        return list(set(normalized))  # Remove duplicates

    def _normalize_price(self, price: Any) -> Tuple[Optional[Decimal], bool]:
        """Normalize raw price values and apply validation/corrections."""
        decimal_price = self._parse_price_value(price)
        if decimal_price is None:
            return None, False

        try:
            normalized, corrected = self.validate_price(decimal_price)
            return normalized, corrected
        except ValidationError as exc:
            logger.warning("Price validation failed (%s): %s", price, exc)
            return None, False

    def _parse_price_value(self, price: Any) -> Optional[Decimal]:
        """Parse a raw price representation into Decimal."""
        if price is None or price == "":
            return None

        try:
            if isinstance(price, str):
                cleaned = price.strip()
                cleaned = re.sub(r'[€$£]', '', cleaned)
                cleaned = cleaned.replace(' ', '')
                if ',' in cleaned and '.' not in cleaned and re.match(r'^[0-9]+,[0-9]{1,2}$', cleaned):
                    cleaned = cleaned.replace(',', '.')
                else:
                    cleaned = cleaned.replace(',', '')
                if cleaned == '':
                    return None
                return Decimal(cleaned)

            if isinstance(price, (int, float, Decimal)):
                return Decimal(str(price))
        except (InvalidOperation, ValueError, TypeError) as exc:
            logger.warning("Failed to parse price '%s': %s", price, exc)

        return None

    def validate_price(self, price: Decimal) -> Tuple[Decimal, bool]:
        """Enforce business rules for prices and auto-correct obvious OCR issues."""
        corrected = False
        if price >= Decimal('100'):
            if (price % 10) == 0:
                corrected_price = price / Decimal('100')
                logger.warning("Auto-corrected price %s -> %s", price, corrected_price)
                price = corrected_price
                corrected = True
            else:
                raise ValidationError("Price %s exceeds allowed maximum for a menu item" % price)

        if price > Decimal('50'):
            logger.warning("Suspiciously high price detected: %s", price)

        return price, corrected

    def _normalize_category(self, category: Any) -> str:
        """Normalize or default a category name."""
        if not category:
            return 'Main dishes'
        normalized = str(category).strip()
        return normalized if normalized else 'Main dishes'

    def _normalize_item_name(self, name: Any) -> str:
        """Normalize item names for duplicate detection."""
        if not name:
            return ''
        return str(name).strip().lower()

    def _detect_currency(self, raw_value: str) -> str:
        """Detect a common currency symbol or keyword from a string."""
        if not raw_value:
            return ''

        lower_value = raw_value.lower()
        if '€' in raw_value or 'eur' in lower_value or 'euro' in lower_value:
            return '€'
        if '$' in raw_value or 'usd' in lower_value or 'dollar' in lower_value:
            return '$'
        if '£' in raw_value or 'gbp' in lower_value or 'pound' in lower_value:
            return '£'

        return ''

    def _normalize_currency(self, currency: Any) -> str:
        """Normalize currency values to supported symbols."""
        symbol = str(currency).strip() if currency is not None else ''
        if not symbol:
            return ''
        if '€' in symbol or symbol.lower() in ['eur', 'euro']:
            return '€'
        if '$' in symbol or symbol.lower() in ['usd', 'dollar']:
            return '$'
        if '£' in symbol or symbol.lower() in ['gbp', 'pound']:
            return '£'
        return ''

    def create_foodtruck_from_import(self, import_instance: OnboardingImport) -> Dict[str, Any]:
        """
        Create FoodTruck, Menu, and related entities from parsed data.

        Uses transaction.atomic for safety.
        Does NOT overwrite existing data.
        Allows partial creation.
        """
        if import_instance.status != 'completed':
            raise ValidationError("Import must be completed before creating a food truck")

        if not import_instance.parsed_data:
            raise ValidationError("No parsed data available")

        data = import_instance.parsed_data

        try:
            with transaction.atomic():
                # Create FoodTruck
                foodtruck_data = data.get('foodtruck', {})
                foodtruck = FoodTruck.objects.create(
                    owner=import_instance.user,
                    default_language=self._normalize_language_code(foodtruck_data.get('language_code')),
                    name=foodtruck_data.get('name', 'My Food Truck'),
                    description=foodtruck_data.get('description', ''),
                    latitude=foodtruck_data.get('latitude', 0.0),
                    longitude=foodtruck_data.get('longitude', 0.0),
                    primary_color=foodtruck_data.get('primary_color', '#000000'),
                    secondary_color=foodtruck_data.get('secondary_color', '#FFFFFF'),
                )

                # Assign preferences
                preferences = foodtruck_data.get('preferences', [])
                for pref_name in preferences:
                    try:
                        pref = Preference.objects.get(name=pref_name)
                        foodtruck.supported_preferences.add(pref)
                    except Preference.DoesNotExist:
                        logger.warning(f"Preference '{pref_name}' not found, skipping")

                # Create Menu
                menu = Menu.objects.create(
                    food_truck=foodtruck,
                    name=foodtruck.get_default_menu_name()
                )

                # Create Categories and Items
                menu_data = data.get('menu', [])
                for category_data in menu_data:
                    category = Category.objects.create(
                        menu=menu,
                        name=category_data.get('category', 'General')
                    )

                    for item_data in category_data.get('items', []):
                        # Parse price, handling various formats
                        price_str = item_data.get('price', '0')
                        if isinstance(price_str, str):
                            # Remove currency symbols and parse
                            price_str = price_str.replace('€', '').replace('$', '').strip()
                            try:
                                price = float(price_str)
                            except ValueError:
                                price = 0.00
                        else:
                            price = float(price_str) if price_str else 0.00

                        item = Item.objects.create(
                            category=category,
                            name=item_data.get('name', 'Unnamed Item'),
                            description=item_data.get('description', ''),
                            base_price=price
                        )

                        # Create options if any
                        for option_data in item_data.get('options', []):
                            option_group, _ = OptionGroup.objects.get_or_create(
                                category=category,
                                name=option_data.get('group', 'Options')
                            )
                            option = Option.objects.create(
                                group=option_group,
                                name=option_data.get('name', ''),
                                price_modifier=option_data.get('price') or 0,
                            )
                            option.items.add(item)

                # Apply branding
                branding = data.get('branding', {})
                if branding:
                    foodtruck.primary_color = branding.get('primary_color', foodtruck.primary_color)
                    foodtruck.secondary_color = branding.get('secondary_color', foodtruck.secondary_color)
                    foodtruck.save()

                return {
                    'status': 'success',
                    'foodtruck_id': foodtruck.id,
                    'message': f'Successfully created FoodTruck "{foodtruck.name}" with menu'
                }

        except Exception as e:
            logger.error(f"Error creating entities from import {import_instance.id}: {str(e)}")
            raise ValidationError(f"Failed to create entities: {str(e)}")

    def _get_empty_structure(self) -> Dict[str, Any]:
        """Return empty JSON structure."""
        branding_defaults = {
            "primary_color": {"name": "", "hex": ""},
            "secondary_color": {"name": "", "hex": ""},
            "style": ""
        }
        return {
            "foodtruck": {
                "language_code": settings.LANGUAGE_CODE,
                "name": "",
                "description": "",
                "cuisine_type": "",
                "possible_location": "",
                "preferences": []
            },
            "menu": [],
            "branding": self.normalize_colors(branding_defaults)
        }

    def _build_text_extraction_prompt(self, text: str) -> str:
        """Build the OpenAI prompt for text extraction."""
        return f"""
You are an AI assistant helping users set up their food truck business. Extract structured information from the provided text.

IMPORTANT RULES:
- Return ONLY valid JSON
- Do NOT hallucinate or add information not in the text
- If data is missing, use empty strings or empty arrays
- Be conservative - only extract what's clearly present
- Detect the dominant language of the business content and return it as one of: en, fr, es

Input text:
{text}

Return JSON in this exact format:
{{
  "foodtruck": {{
        "language_code": "en",
    "name": "",
    "description": "",
    "cuisine_type": "",
    "possible_location": "",
    "preferences": []
  }},
  "menu": [
    {{
      "category": "",
      "items": [
        {{
          "name": "",
          "description": "",
          "price": null,
          "currency": "",
          "options": []
        }}
      ]
    }}
  ],
  "branding": {{
    "primary_color": {{"name": "", "hex": ""}},
    "secondary_color": {{"name": "", "hex": ""}},
    "style": ""
  }}
}}
"""

    def _build_menu_image_prompt(self) -> str:
        """Build the OpenAI prompt for menu image analysis."""
        return """
You are analyzing a food menu image.

Extract ALL visible structured data.

Rules:
- Do NOT guess missing values
- Do NOT invent items
- Use null for missing prices
- Group items by category if visible
- Extract colors if dominant colors are visible
- Detect currency (€,$,£)
- Detect the dominant language of the menu and return it as one of: en, fr, es
- Return ONLY valid JSON

Return JSON in this exact format:
{
    "foodtruck": {
        "language_code": "en"
    },
  "menu": [
    {
      "category": "",
      "items": [
        {
          "name": "",
          "description": "",
          "price": null,
          "currency": ""
        }
      ]
    }
  ],
  "branding": {
    "primary_color": {"name": "", "hex": ""},
    "secondary_color": {"name": "", "hex": ""}
  }
}
"""

    def _build_logo_analysis_prompt(self) -> str:
        """Build the OpenAI prompt for logo color extraction."""
        return """
Extract dominant brand colors from this logo.

Rules:
- Return 1 or 2 main colors
- Provide HEX values only
- Ignore background noise
- Prefer high contrast / visible colors
- Return ONLY valid JSON

Return:
{
  "primary_color": "#XXXXXX",
  "secondary_color": "#XXXXXX"
}
"""

    def generate_foodtruck(self, concept_prompt: str, language_code: Optional[str] = None) -> Dict[str, Any]:
        """
        Generate a complete foodtruck concept from a user prompt.

        Args:
            concept_prompt: User's description of their foodtruck idea

        Returns:
            Dict containing generated foodtruck data with name, description, and menu
        """
        if not concept_prompt or not concept_prompt.strip():
            raise ValidationError("Concept prompt cannot be empty")

        normalized_language = self._normalize_language_code(language_code)
        prompt = self._build_foodtruck_generation_prompt(concept_prompt.strip(), normalized_language)

        try:
            response = self.openai_service.generate(
                prompt=prompt,
                model="gpt-4o",
                max_tokens=3000
            )

            # Clean the response - sometimes OpenAI returns markdown code blocks
            cleaned_response = response.strip()
            if cleaned_response.startswith('```json'):
                cleaned_response = cleaned_response[7:]
            if cleaned_response.endswith('```'):
                cleaned_response = cleaned_response[:-3]
            cleaned_response = cleaned_response.strip()

            # Parse JSON response
            data = json.loads(cleaned_response)

            # Validate the response structure
            if not self._validate_generated_data(data):
                logger.warning("Generated data failed validation, using fallback")
                return self._get_fallback_foodtruck(concept_prompt, normalized_language)

            data.setdefault('foodtruck', {})['language_code'] = normalized_language

            return data

        except (json.JSONDecodeError, ValueError) as e:
            logger.error(f"Failed to parse OpenAI response for foodtruck generation: {e}")
            logger.error(f"Raw response was: {response}")
            return self._get_fallback_foodtruck(concept_prompt, normalized_language)
        except Exception as e:
            logger.error(f"Error generating foodtruck: {e}")
            return self._get_fallback_foodtruck(concept_prompt, normalized_language)

    def _build_foodtruck_generation_prompt(self, concept: str, language_code: str) -> str:
        """Build the OpenAI prompt for foodtruck generation."""
        language_name = self._get_language_name(language_code)
        return f"""
You are a creative food truck business consultant. Generate a complete food truck concept based on the user's idea.

USER CONCEPT: {concept}

TARGET LANGUAGE:
- Write all food truck, category and item content in {language_name}
- Return foodtruck.language_code as \"{language_code}\"

Create a compelling food truck concept with:
1. A catchy, memorable name
2. An engaging description that captures the essence
3. A complete menu with 3-5 categories and 2-4 items per category
4. Realistic pricing appropriate for the concept
5. Dietary preferences that fit the concept

IMPORTANT RULES:
- Return ONLY valid JSON
- Make the concept unique and marketable
- Ensure prices are reasonable (most items $5-15)
- Include variety in menu items
- Consider the target audience from the concept
- Keep descriptions concise but appealing

Return JSON in this exact format:
{{
  "foodtruck": {{
        "language_code": "{language_code}",
    "name": "Catchy Food Truck Name",
    "description": "Engaging 2-3 sentence description",
    "cuisine_type": "Primary cuisine style",
    "preferences": ["Vegan", "Gluten-Free", "Halal", "Kosher", "Dairy-Free"]
  }},
  "menu": [
    {{
      "category": "Appetizers",
      "items": [
        {{
          "name": "Item Name",
          "description": "Brief description",
          "price": 8.99,
          "options": []
        }}
      ]
    }}
  ]
}}
"""

    def _validate_generated_data(self, data: Dict) -> bool:
        """Validate the structure of generated foodtruck data."""
        try:
            # Check required top-level keys
            if 'foodtruck' not in data or 'menu' not in data:
                return False

            # Check foodtruck structure
            ft = data['foodtruck']
            if not all(key in ft for key in ['name', 'description', 'cuisine_type', 'preferences']):
                return False

            if not ft['name'] or not ft['description']:
                return False

            # Check menu structure
            if not isinstance(data['menu'], list) or len(data['menu']) == 0:
                return False

            for category in data['menu']:
                if 'category' not in category or 'items' not in category:
                    return False
                if not isinstance(category['items'], list) or len(category['items']) == 0:
                    return False

                for item in category['items']:
                    if not all(key in item for key in ['name', 'description', 'price']):
                        return False
                    if not item['name'] or item['price'] is None:
                        return False

            return True

        except Exception:
            return False

    def _get_fallback_foodtruck(self, concept: str, language_code: Optional[str] = None) -> Dict[str, Any]:
        """Return a basic fallback foodtruck structure when generation fails."""
        normalized_language = self._normalize_language_code(language_code)
        fallback_copy = {
            'en': {
                'name': 'My Food Truck',
                'description': f"A delicious food truck serving {concept.lower() if concept else 'great food'}.",
                'cuisine_type': 'American',
                'preferences': ['Vegetarian'],
                'category': 'Main Dishes',
                'item_name': 'Signature Dish',
                'item_description': 'Our most popular item',
            },
            'fr': {
                'name': 'Mon Food Truck',
                'description': f"Un food truck gourmand qui propose {concept.lower() if concept else 'une cuisine savoureuse'}.",
                'cuisine_type': 'Americaine',
                'preferences': ['Vegetarian'],
                'category': 'Plats principaux',
                'item_name': 'Plat signature',
                'item_description': 'Notre plat le plus populaire',
            },
            'es': {
                'name': 'Mi Food Truck',
                'description': f"Un food truck delicioso que sirve {concept.lower() if concept else 'comida sabrosa'}.",
                'cuisine_type': 'Americana',
                'preferences': ['Vegetarian'],
                'category': 'Platos principales',
                'item_name': 'Plato estrella',
                'item_description': 'Nuestro plato mas popular',
            },
        }
        localized = fallback_copy.get(normalized_language, fallback_copy['en'])
        return {
            "foodtruck": {
                "language_code": normalized_language,
                "name": localized['name'],
                "description": localized['description'],
                "cuisine_type": localized['cuisine_type'],
                "preferences": localized['preferences']
            },
            "menu": [
                {
                    "category": localized['category'],
                    "items": [
                        {
                            "name": localized['item_name'],
                            "description": localized['item_description'],
                            "price": 12.99,
                            "options": []
                        }
                    ]
                }
            ]
        }
