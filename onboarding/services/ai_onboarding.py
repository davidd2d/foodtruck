import json
import logging
from typing import Dict, List, Any, Optional
from django.db import transaction
from django.core.exceptions import ValidationError
from config.services.openai_client import OpenAIService
from onboarding.models import OnboardingImport
from foodtrucks.models import FoodTruck
from menu.models import Menu, Category, Item, OptionGroup, Option
from preferences.models import Preference

logger = logging.getLogger(__name__)


class AIOnboardingService:
    """Service for AI-powered onboarding data processing and entity creation."""

    def __init__(self):
        self.openai_service = OpenAIService()

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
            image_data = {}
            if import_instance.images:
                image_data = self._analyze_images(import_instance.images)

            # Step 4: Merge results
            merged_data = self._merge_data(text_data, image_data)

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
                model="gpt-4",  # Use GPT-4 for better JSON handling
                max_tokens=2000
            )

            # Parse JSON response
            data = json.loads(response.strip())
            return data

        except (json.JSONDecodeError, ValueError) as e:
            logger.warning(f"Failed to parse OpenAI response: {e}")
            return self._get_empty_structure()

    def _analyze_images(self, images: List[str]) -> Dict[str, Any]:
        """Analyze images using OpenAI Vision."""
        if not images:
            return {}

        # For simplicity, analyze the first image
        # In production, you might want to analyze multiple images
        image_path = images[0] if images else None

        if not image_path:
            return {}

        prompt = self._build_image_analysis_prompt()

        try:
            # Note: This assumes OpenAI Vision API integration
            # You may need to adjust based on actual OpenAI client implementation
            response = self.openai_service.generate(
                prompt=prompt,
                model="gpt-4-vision-preview",  # Assuming vision model
                max_tokens=1000
            )

            data = json.loads(response.strip())
            return data

        except Exception as e:
            logger.warning(f"Failed to analyze images: {e}")
            return {}

    def _merge_data(self, text_data: Dict, image_data: Dict) -> Dict:
        """Merge text and image analysis results."""
        merged = text_data.copy()

        # Merge menu items from images
        if 'menu' in image_data and image_data['menu']:
            for img_category in image_data['menu']:
                # Find matching category or add new
                existing_category = None
                for cat in merged.get('menu', []):
                    if cat.get('category', '').lower() == img_category.get('category', '').lower():
                        existing_category = cat
                        break

                if existing_category:
                    # Merge items
                    existing_items = existing_category.get('items', [])
                    img_items = img_category.get('items', [])
                    existing_items.extend(img_items)
                    existing_category['items'] = existing_items
                else:
                    merged.setdefault('menu', []).append(img_category)

        # Merge branding from images
        if 'branding' in image_data:
            merged.setdefault('branding', {}).update(image_data['branding'])

        return merged

    def _normalize_data(self, data: Dict) -> Dict:
        """Normalize and clean the extracted data."""
        normalized = data.copy()

        # Normalize preferences
        if 'foodtruck' in normalized and 'preferences' in normalized['foodtruck']:
            normalized['foodtruck']['preferences'] = self._normalize_preferences(
                normalized['foodtruck']['preferences']
            )

        # Normalize menu prices and categories
        if 'menu' in normalized:
            for category in normalized['menu']:
                if 'items' in category:
                    for item in category['items']:
                        if 'price' in item:
                            item['price'] = self._normalize_price(item['price'])

        return normalized

    def _normalize_preferences(self, preferences: List[str]) -> List[str]:
        """Map text preferences to existing Preference objects."""
        if not preferences:
            return []

        normalized = []
        existing_prefs = {pref.name.lower(): pref.name for pref in Preference.objects.all()}

        for pref in preferences:
            pref_lower = pref.lower().strip()
            if pref_lower in existing_prefs:
                normalized.append(existing_prefs[pref_lower])
            else:
                # Keep original if no match found
                normalized.append(pref.strip())

        return list(set(normalized))  # Remove duplicates

    def _normalize_price(self, price: Any) -> Optional[float]:
        """Normalize price to float, handling various formats."""
        if price is None or price == "":
            return None

        try:
            # Remove currency symbols and convert to float
            if isinstance(price, str):
                # Remove common currency symbols and commas
                cleaned = price.replace('$', '').replace('€', '').replace('£', '').replace(',', '')
                return float(cleaned.strip())
            return float(price)
        except (ValueError, TypeError):
            return None

    def create_foodtruck_from_import(self, import_instance: OnboardingImport) -> Dict[str, Any]:
        """
        Create FoodTruck, Menu, and related entities from parsed data.

        Uses transaction.atomic for safety.
        Does NOT overwrite existing data.
        Allows partial creation.
        """
        if not import_instance.parsed_data:
            raise ValidationError("No parsed data available")

        data = import_instance.parsed_data

        try:
            with transaction.atomic():
                # Create FoodTruck
                foodtruck_data = data.get('foodtruck', {})
                foodtruck = FoodTruck.objects.create(
                    user=import_instance.user,
                    name=foodtruck_data.get('name', 'My Food Truck'),
                    description=foodtruck_data.get('description', ''),
                    cuisine_type=foodtruck_data.get('cuisine_type', ''),
                    location=foodtruck_data.get('possible_location', ''),
                )

                # Assign preferences
                preferences = foodtruck_data.get('preferences', [])
                for pref_name in preferences:
                    try:
                        pref = Preference.objects.get(name=pref_name)
                        foodtruck.preferences.add(pref)
                    except Preference.DoesNotExist:
                        logger.warning(f"Preference '{pref_name}' not found, skipping")

                # Create Menu
                menu = Menu.objects.create(
                    foodtruck=foodtruck,
                    name=f"{foodtruck.name} Menu"
                )

                # Create Categories and Items
                menu_data = data.get('menu', [])
                for category_data in menu_data:
                    category = Category.objects.create(
                        menu=menu,
                        name=category_data.get('category', 'General')
                    )

                    for item_data in category_data.get('items', []):
                        item = Item.objects.create(
                            category=category,
                            name=item_data.get('name', 'Unnamed Item'),
                            description=item_data.get('description', ''),
                            price=item_data.get('price')
                        )

                        # Create options if any
                        for option_data in item_data.get('options', []):
                            option_group, _ = OptionGroup.objects.get_or_create(
                                item=item,
                                name=option_data.get('group', 'Options')
                            )
                            Option.objects.create(
                                option_group=option_group,
                                name=option_data.get('name', ''),
                                price=option_data.get('price')
                            )

                # Apply branding (if we had branding fields on FoodTruck)
                # For now, just log it
                branding = data.get('branding', {})
                logger.info(f"Branding data for {foodtruck.name}: {branding}")

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
        return {
            "foodtruck": {
                "name": "",
                "description": "",
                "cuisine_type": "",
                "possible_location": "",
                "preferences": []
            },
            "menu": [],
            "branding": {
                "primary_color": "",
                "secondary_color": "",
                "style": ""
            }
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

Input text:
{text}

Return JSON in this exact format:
{{
  "foodtruck": {{
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
          "options": []
        }}
      ]
    }}
  ],
  "branding": {{
    "primary_color": "",
    "secondary_color": "",
    "style": ""
  }}
}}
"""

    def _build_image_analysis_prompt(self) -> str:
        """Build the OpenAI prompt for image analysis."""
        return """
Analyze this food truck related image and extract relevant information.

Return JSON in the same format as text extraction, focusing on:
- Menu items visible in the image
- Any branding elements (colors, style)
- Food truck name if visible

If no relevant information is found, return empty structure.
"""