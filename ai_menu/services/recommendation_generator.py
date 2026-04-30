"""
AI Recommendation Generator Service.

Generates AI-powered recommendations for menu items using OpenAI,
with fallback to rule-based analysis if API calls fail.
"""
import json
import logging
import re
from decimal import Decimal
from typing import Dict, Any, List, Optional

from django.conf import settings
from django.db import transaction
from django.core.exceptions import ValidationError

from config.services.openai_client import OpenAIService
from ai_menu.models import AIRecommendation
from ai_menu.services.menu_analyzer import MenuAnalyzerService
from menu.models import Option

logger = logging.getLogger(__name__)


class AIRecommendationGeneratorService:
    """
    Service for generating AI-powered menu item recommendations.

    This service:
    1. Prepares menu item context (description, category, price, etc.)
    2. Builds a structured prompt for OpenAI
    3. Calls OpenAI API via OpenAIService
    4. Parses and validates the response
    5. Persists recommendations to database
    6. Falls back to rule-based analysis if API fails

    The prompt asks OpenAI to generate:
    - Detected item category (burger, bowl, taco, salad, etc.)
    - Free option suggestions (realistic, no price impact)
    - Paid upsell suggestions (realistic pricing)
    - Bundle/combo suggestions
    """

    RECOMMENDATION_MODEL = "gpt-4o"
    MAX_TOKENS = 1500
    TIMEOUT_SECONDS = 30
    LANGUAGE_NAMES = {
        'en': 'English',
        'fr': 'French',
        'es': 'Spanish',
    }

    def __init__(self):
        """Initialize service with OpenAIService client."""
        self.openai_service = OpenAIService()
        self.fallback_service = MenuAnalyzerService()

    def generate_and_store_for_item(self, item) -> Dict[str, Any]:
        """
        Generate recommendations for a menu item and store them.

        This is the main public method. It:
        1. Attempts to generate recommendations via OpenAI
        2. Falls back to rule-based analysis if API fails
        3. Stores all recommendations as pending AIRecommendation records
        4. Clears existing pending recommendations for this item first

        Args:
            item: menu.Item instance

        Returns:
            Dict with keys:
            - 'status': 'success' or 'fallback' or 'error'
            - 'recommendations': List of created AIRecommendation IDs
            - 'error': Error message (if status is 'error')
            - 'fallback_reason': Reason for fallback (if status is 'fallback')

        Raises:
            ValidationError: If item is invalid or database error occurs
        """
        if not item or not item.pk:
            raise ValidationError("Item must be a valid saved instance")

        try:
            with transaction.atomic():
                # Clear old pending recommendations
                self._clear_pending_recommendations(item)

                # Try AI generation first
                recommendations_data = self._generate_via_openai(item)

                # If API failed, use fallback
                if recommendations_data is None:
                    recommendations_data = self._generate_via_fallback(item)
                    fallback_used = True
                else:
                    fallback_used = False

                recommendations_data = self._ensure_option_review_coverage(item, recommendations_data)

                # Store recommendations
                created_ids = self._persist_recommendations(item, recommendations_data)

                status = 'fallback' if fallback_used else 'success'
                result = {
                    'status': status,
                    'recommendations': created_ids,
                }

                if fallback_used:
                    result['fallback_reason'] = 'OpenAI API call failed or returned invalid data'

                logger.info(
                    f"Generated {len(created_ids)} recommendations for item {item.id} ({item.name}) - status: {status}"
                )
                return result

        except Exception as e:
            logger.exception(f"Error generating recommendations for item {item.id}: {str(e)}")
            return {
                'status': 'error',
                'error': str(e),
                'recommendations': [],
            }

    def _clear_pending_recommendations(self, item):
        """
        Delete existing pending recommendations for an item.

        This ensures we don't accumulate old pending recommendations
        when regenerating for the same item.

        Args:
            item: menu.Item instance
        """
        deleted_count, _ = AIRecommendation.objects.for_item(item).pending().delete()
        if deleted_count > 0:
            logger.info(f"Cleared {deleted_count} pending recommendations for item {item.id}")

    def _generate_via_openai(self, item) -> Optional[Dict[str, Any]]:
        """
        Attempt to generate recommendations via OpenAI API.

        Returns None if API call fails or returns invalid JSON.

        Args:
            item: menu.Item instance

        Returns:
            Dict with structure:
            {
                'detected_category': str,
                'free_options': [{'name': str, 'reason': str}, ...],
                'paid_options': [{'name': str, 'suggested_price': float, 'reason': str}, ...],
                'bundles': [{'name': str, 'items': [str, ...], 'reason': str}, ...]
            }
            Or None if generation failed.
        """
        try:
            # Prepare context
            context = self._prepare_item_context(item)

            # Build prompt
            prompt = self._build_ai_prompt(item, context)

            # Call OpenAI
            logger.debug(f"Calling OpenAI for item {item.id}")
            response = self.openai_service.generate(
                prompt=prompt,
                model=self.RECOMMENDATION_MODEL,
                max_tokens=self.MAX_TOKENS,
                use_cache=False,  # Don't cache recommendations
            )

            # Parse response
            recommendations_data = self._parse_openai_response(response)

            # Validate response
            if self._validate_recommendations_data(recommendations_data):
                logger.info(f"Successfully generated AI recommendations for item {item.id}")
                return recommendations_data
            else:
                logger.warning(f"OpenAI response validation failed for item {item.id}")
                return None

        except Exception as e:
            logger.warning(f"OpenAI API call failed for item {item.id}: {str(e)}")
            return None

    def _generate_via_fallback(self, item) -> Dict[str, Any]:
        """
        Generate recommendations using rule-based fallback service.

        Args:
            item: menu.Item instance

        Returns:
            Dict with MVP recommendations from MenuAnalyzerService,
            converted to the same structure as OpenAI response.
        """
        logger.info(f"Using fallback rule-based analysis for item {item.id}")

        try:
            language_code = self._get_language_code(item)
            fallback_result = self.fallback_service.analyze_item(item, language_code=language_code)
            fallback_reason = self._get_fallback_reason(language_code)

            # Convert fallback format to OpenAI format
            return {
                'detected_category': fallback_result.get('detected_category', 'other'),
                'free_options': [
                    {'name': opt, 'reason': fallback_reason}
                    for opt in fallback_result.get('free_options_suggestions', [])
                ],
                'paid_options': [
                    {
                        'name': opt.split(' (+')[0] if ' (+' in opt else opt,  # Remove price
                        'suggested_price': self._extract_price_from_string(opt),
                        'reason': fallback_reason
                    }
                    for opt in fallback_result.get('paid_options_suggestions', [])
                ],
                'bundles': [
                    {'name': bundle, 'items': [], 'reason': fallback_reason}
                    for bundle in fallback_result.get('bundles_suggestions', [])
                ],
            }
        except Exception as e:
            logger.exception(f"Fallback generation also failed for item {item.id}: {str(e)}")
            # Return empty structure on complete failure
            return {
                'detected_category': 'other',
                'free_options': [],
                'paid_options': [],
                'bundles': [],
            }

    def _prepare_item_context(self, item) -> Dict[str, Any]:
        """
        Prepare structured context for the item.

        Includes item details, category, menu, and foodtruck info.

        Args:
            item: menu.Item instance

        Returns:
            Dict with item context
        """
        try:
            category = item.category
            menu = category.menu
            foodtruck = menu.food_truck

            return {
                'item_name': item.name,
                'item_description': item.description or '',
                'item_base_price': float(item.base_price),
                'category_name': category.name,
                'menu_name': menu.name,
                'foodtruck_name': foodtruck.name,
                'foodtruck_language': self._get_language_code(item),
                'foodtruck_cuisine': getattr(foodtruck, 'cuisine_type', 'Mixed'),
                'category_options': self._build_category_options_context(item),
            }
        except Exception as e:
            logger.warning(f"Error preparing context for item {item.id}: {str(e)}")
            return {
                'item_name': item.name,
                'item_description': item.description or '',
                'item_base_price': float(item.base_price),
                'category_name': item.category.name,
                'foodtruck_language': settings.LANGUAGE_CODE,
                'category_options': [],
            }

    def _build_category_options_context(self, item) -> List[Dict[str, Any]]:
        """Return lightweight option metadata for prompt grounding."""
        options = (
            Option.objects
            .filter(group__category=item.category)
            .select_related('group')
            .prefetch_related('items')
            .order_by('group__name', 'name')
        )

        rows = []
        for option in options:
            rows.append({
                'id': option.id,
                'name': option.name,
                'group_name': option.group.name,
                'price_modifier': float(option.price_modifier),
                'enabled_for_item': option.items.filter(pk=item.pk).exists(),
                'is_available': option.is_available,
            })

        # Keep prompt size bounded for large menus.
        return rows[:60]

    def _build_ai_prompt(self, item, context: Dict[str, Any]) -> str:
        """
        Build the structured prompt for OpenAI.

        Args:
            item: menu.Item instance
            context: Prepared item context

        Returns:
            Prompt string
        """
        language_code = context.get('foodtruck_language', settings.LANGUAGE_CODE)
        language_name = self.LANGUAGE_NAMES.get(language_code, self.LANGUAGE_NAMES['en'])
        category_options = context.get('category_options', [])
        if category_options:
            options_lines = '\n'.join([
                f"- id={row['id']} | group={row['group_name']} | name={row['name']} | "
                f"price_modifier={row['price_modifier']:.2f} | enabled_for_item={str(row['enabled_for_item']).lower()} | "
                f"globally_available={str(row['is_available']).lower()}"
                for row in category_options
            ])
        else:
            options_lines = '- none'

        return f"""
    You are an expert menu consultant helping food truck owners optimize their menus.

Analyze this menu item and generate actionable recommendations.

    OUTPUT LANGUAGE:
    - All customer-facing suggestion names, reasons, and bundle item labels must be written in {language_name}
    - Keep detected_category in English and choose only from the allowed enum values

ITEM DETAILS:
- Name: {context['item_name']}
- Description: {context['item_description'] or '(no description)'}
- Base Price: €{context['item_base_price']:.2f}
- Category: {context['category_name']}
- Menu: {context['menu_name']}
- Food Truck: {context['foodtruck_name']}

REQUIREMENTS:
1. Detect the item category (burger, bowl, taco, salad, sandwich, pizza, dessert, drink, side, other)
2. Suggest FREE options that enhance value perception (max 3-4)
3. Suggest PAID upsells that increase revenue (max 3-4, realistic pricing)
4. Suggest BUNDLES/combos that increase average order value (max 2-3)
5. Review EXISTING category options and critique whether each one should be enabled or disabled for this specific item
6. In option_reviews, include all options where enabled_for_item=true (with enable/disable/keep and a reason)

EXISTING CATEGORY OPTIONS:
{options_lines}

CONSTRAINTS:
- All suggestions must be realistic for this item type
- Free options: no price impact
- Paid options: reasonable pricing (+€0.50 to +€4.00 typical range)
- All prices must be reasonable for the food truck industry
- Be conservative: better to suggest 1 great option than 3 mediocre ones
- Do not duplicate an existing option name in new suggestions when an existing option can be reused
- In option_reviews, use existing_option_id values from the provided list
- Return ONLY valid JSON, no markdown or extra text

Return JSON in EXACTLY this format:
{{
  "detected_category": "burger",
  "free_options": [
    {{"name": "Extra lettuce", "reason": "Adds freshness at no cost"}},
    {{"name": "Extra sauce on the side", "reason": "Enhances customer satisfaction"}}
  ],
  "paid_options": [
    {{"name": "Add bacon", "suggested_price": 1.50, "reason": "Popular premium upgrade"}},
    {{"name": "Double patty", "suggested_price": 3.00, "reason": "High-demand upsell"}}
  ],
  "bundles": [
    {{"name": "Burger + Fries + Drink combo", "items": ["Burger", "Fries", "Drink"], "reason": "Increases average order value by 20-25%"}},
    {{"name": "Burger + Appetizer combo", "items": ["Burger", "Appetizer"], "reason": "Encourages larger purchases"}}
    ],
    "option_reviews": [
        {{"existing_option_id": 101, "name": "Extra pickles", "suggested_action": "enable", "reason": "Good fit for this item", "current_status": "disabled", "option_type": "free_option"}},
        {{"existing_option_id": 102, "name": "Spicy sauce", "suggested_action": "disable", "reason": "Not aligned with flavor profile", "current_status": "enabled", "option_type": "paid_option"}}
  ]
}}

IMPORTANT: Return ONLY the JSON object, no explanation or markdown code blocks.
"""

    def _parse_openai_response(self, response: str) -> Optional[Dict[str, Any]]:
        """
        Parse OpenAI response and extract JSON.

        Handles various response formats (with/without markdown code blocks).

        Args:
            response: Raw response from OpenAI

        Returns:
            Parsed dict or None if parsing fails
        """
        if not response or not response.strip():
            logger.warning("Empty response from OpenAI")
            return None

        try:
            cleaned = response.strip()

            # Remove markdown code blocks if present
            if cleaned.startswith('```json'):
                cleaned = cleaned[7:]
            if cleaned.startswith('```'):
                cleaned = cleaned[3:]
            if cleaned.endswith('```'):
                cleaned = cleaned[:-3]

            cleaned = cleaned.strip()

            # Parse JSON
            data = json.loads(cleaned)
            return data

        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse OpenAI JSON response: {str(e)}")
            logger.debug(f"Response was: {response[:200]}...")
            return None
        except Exception as e:
            logger.exception(f"Unexpected error parsing OpenAI response: {str(e)}")
            return None

    def _validate_recommendations_data(self, data: Optional[Dict[str, Any]]) -> bool:
        """
        Validate recommendations data structure.

        Args:
            data: Data to validate

        Returns:
            True if valid, False otherwise
        """
        if not data or not isinstance(data, dict):
            logger.warning("Data is not a dict")
            return False

        # Check required keys
        required_keys = {'detected_category', 'free_options', 'paid_options', 'bundles'}
        if not required_keys.issubset(data.keys()):
            logger.warning(f"Missing required keys. Expected {required_keys}, got {set(data.keys())}")
            return False

        # Validate detected_category
        if not isinstance(data['detected_category'], str) or not data['detected_category'].strip():
            logger.warning("detected_category must be a non-empty string")
            return False

        # Validate lists
        for key in ['free_options', 'paid_options', 'bundles']:
            if not isinstance(data[key], list):
                logger.warning(f"{key} must be a list")
                return False

            for item in data[key]:
                if not isinstance(item, dict):
                    logger.warning(f"{key} items must be dicts")
                    return False

        # Validate free_options items
        for opt in data['free_options']:
            if 'name' not in opt or 'reason' not in opt:
                logger.warning("free_options items must have 'name' and 'reason'")
                return False

        # Validate paid_options items
        for opt in data['paid_options']:
            if not all(k in opt for k in ['name', 'suggested_price', 'reason']):
                logger.warning("paid_options items must have 'name', 'suggested_price', 'reason'")
                return False

        # Validate bundles items
        for bundle in data['bundles']:
            if not all(k in bundle for k in ['name', 'items', 'reason']):
                logger.warning("bundles items must have 'name', 'items', 'reason'")
                return False

        # Validate optional option reviews
        option_reviews = data.get('option_reviews', [])
        if option_reviews is None:
            option_reviews = []
        if not isinstance(option_reviews, list):
            logger.warning("option_reviews must be a list")
            return False
        for review in option_reviews:
            if not isinstance(review, dict):
                logger.warning("option_reviews items must be dicts")
                return False
            expected = {'existing_option_id', 'name', 'suggested_action', 'reason', 'current_status', 'option_type'}
            if not expected.issubset(review.keys()):
                logger.warning("option_reviews items must include existing_option_id, name, suggested_action, reason, current_status, option_type")
                return False
            if review.get('suggested_action') not in {'enable', 'disable', 'keep'}:
                logger.warning("option_reviews.suggested_action must be enable, disable, or keep")
                return False
            if review.get('option_type') not in {'free_option', 'paid_option'}:
                logger.warning("option_reviews.option_type must be free_option or paid_option")
                return False

        return True

    def _persist_recommendations(self, item, recommendations_data: Dict[str, Any]) -> List[int]:
        """
        Create and store AIRecommendation records from parsed data.

        Creates separate recommendations for each suggestion type.

        Args:
            item: menu.Item instance
            recommendations_data: Parsed recommendations from OpenAI

        Returns:
            List of created AIRecommendation IDs
        """
        created_ids = []
        language_code = self._get_language_code(item)
        existing_options_by_name = self._build_existing_options_index(item)
        reviewed_option_ids = set()

        try:
            # Create free option recommendations
            for free_opt in recommendations_data.get('free_options', []):
                existing_option = self._find_existing_option_match(existing_options_by_name, free_opt.get('name', ''))
                if existing_option is not None:
                    reviewed_option_ids.add(existing_option.id)
                    rec = AIRecommendation.objects.create(
                        item=item,
                        recommendation_type='free_option',
                        language_code=language_code,
                        payload=self._build_existing_option_payload(existing_option, item, free_opt.get('reason', '')),
                        status='pending',
                    )
                    created_ids.append(rec.id)
                    logger.debug(f"Converted duplicate free option into existing review recommendation: {rec.id}")
                    continue

                rec = AIRecommendation.objects.create(
                    item=item,
                    recommendation_type='free_option',
                    language_code=language_code,
                    payload={
                        'name': free_opt.get('name', ''),
                        'reason': free_opt.get('reason', ''),
                    },
                    status='pending',
                )
                created_ids.append(rec.id)
                logger.debug(f"Created free_option recommendation: {rec.id}")

            # Create paid option recommendations
            for paid_opt in recommendations_data.get('paid_options', []):
                existing_option = self._find_existing_option_match(existing_options_by_name, paid_opt.get('name', ''))
                if existing_option is not None:
                    reviewed_option_ids.add(existing_option.id)
                    rec = AIRecommendation.objects.create(
                        item=item,
                        recommendation_type='paid_option',
                        language_code=language_code,
                        payload=self._build_existing_option_payload(existing_option, item, paid_opt.get('reason', '')),
                        status='pending',
                    )
                    created_ids.append(rec.id)
                    logger.debug(f"Converted duplicate paid option into existing review recommendation: {rec.id}")
                    continue

                rec = AIRecommendation.objects.create(
                    item=item,
                    recommendation_type='paid_option',
                    language_code=language_code,
                    payload={
                        'name': paid_opt.get('name', ''),
                        'suggested_price': float(paid_opt.get('suggested_price', 0)),
                        'reason': paid_opt.get('reason', ''),
                    },
                    status='pending',
                )
                created_ids.append(rec.id)
                logger.debug(f"Created paid_option recommendation: {rec.id}")

            # Create bundle recommendations
            for bundle in recommendations_data.get('bundles', []):
                rec = AIRecommendation.objects.create(
                    item=item,
                    recommendation_type='bundle',
                    language_code=language_code,
                    payload={
                        'name': bundle.get('name', ''),
                        'items': bundle.get('items', []),
                        'reason': bundle.get('reason', ''),
                    },
                    status='pending',
                )
                created_ids.append(rec.id)
                logger.debug(f"Created bundle recommendation: {rec.id}")

            # Create existing option review recommendations
            for option_review in recommendations_data.get('option_reviews', []):
                existing_option_id = option_review.get('existing_option_id')
                if not existing_option_id:
                    continue

                existing_option = Option.objects.filter(
                    id=existing_option_id,
                    group__category=item.category,
                ).first()
                if existing_option is None:
                    continue

                if existing_option.id in reviewed_option_ids:
                    continue

                reviewed_option_ids.add(existing_option.id)
                recommendation_type = option_review.get('option_type', 'free_option')
                current_status = 'enabled' if (
                    existing_option.items.filter(pk=item.pk).exists() and existing_option.is_available
                ) else 'disabled'
                rec = AIRecommendation.objects.create(
                    item=item,
                    recommendation_type=recommendation_type,
                    language_code=language_code,
                    payload={
                        'name': option_review.get('name', existing_option.name),
                        'reason': option_review.get('reason', ''),
                        'existing_option_id': existing_option.id,
                        'suggested_action': option_review.get('suggested_action', 'keep'),
                        'current_status': current_status,
                    },
                    status='pending',
                )
                created_ids.append(rec.id)
                logger.debug(f"Created option review recommendation: {rec.id}")

        except Exception as e:
            logger.exception(f"Error persisting recommendations for item {item.id}: {str(e)}")
            raise

        return created_ids

    def _build_existing_options_index(self, item):
        """Index category options by normalized name for duplicate detection."""
        index = {}
        options = Option.objects.filter(group__category=item.category).select_related('group')
        for option in options:
            key = self._normalize_option_name(option.name)
            if key and key not in index:
                index[key] = option
        return index

    def _find_existing_option_match(self, existing_options_by_name, candidate_name):
        """Return an existing category option matching a suggested option name."""
        key = self._normalize_option_name(candidate_name)
        if not key:
            return None
        return existing_options_by_name.get(key)

    def _build_existing_option_payload(self, option, item, ai_reason):
        """Build standardized payload for recommendations targeting existing options."""
        is_enabled_for_item = option.items.filter(pk=item.pk).exists()
        current_status = 'enabled' if (is_enabled_for_item and option.is_available) else 'disabled'
        suggested_action = 'keep' if current_status == 'enabled' else 'enable'
        reason = ai_reason or 'This option already exists in the category and can be reused for this item.'
        option_type = 'paid_option' if option.price_modifier > Decimal('0.00') else 'free_option'
        return {
            'name': option.name,
            'reason': reason,
            'existing_option_id': option.id,
            'suggested_action': suggested_action,
            'current_status': current_status,
            'option_type': option_type,
        }

    def _normalize_option_name(self, value):
        """Normalize option names for deterministic duplicate comparison."""
        normalized = (value or '').strip().casefold()
        normalized = re.sub(r'\s+', ' ', normalized)
        return normalized

    def _ensure_option_review_coverage(self, item, recommendations_data):
        """Ensure currently enabled item options all receive an AI review entry."""
        data = dict(recommendations_data or {})
        option_reviews = list(data.get('option_reviews') or [])

        reviewed_ids = set()
        for review in option_reviews:
            if not isinstance(review, dict):
                continue
            option_id = review.get('existing_option_id')
            if option_id:
                reviewed_ids.add(option_id)

        language_code = self._get_language_code(item)
        keep_reason = self._get_option_keep_reason(language_code)
        enabled_options = Option.objects.filter(
            group__category=item.category,
            items=item,
        ).select_related('group').order_by('group__name', 'name')

        for option in enabled_options:
            if option.id in reviewed_ids:
                continue
            option_reviews.append({
                'existing_option_id': option.id,
                'name': option.name,
                'suggested_action': 'keep',
                'reason': keep_reason,
                'current_status': 'enabled',
                'option_type': 'paid_option' if option.price_modifier > Decimal('0.00') else 'free_option',
            })

        data['option_reviews'] = option_reviews
        return data

    def _get_language_code(self, item) -> str:
        """Return the owning food truck content language or the project default."""
        language_code = getattr(item.category.menu.food_truck, 'default_language', settings.LANGUAGE_CODE)
        valid_codes = {code for code, _ in settings.LANGUAGES}
        return language_code if language_code in valid_codes else settings.LANGUAGE_CODE

    def _get_fallback_reason(self, language_code: str) -> str:
        """Return a localized fallback reason."""
        reasons = {
            'en': 'Rule-based suggestion',
            'fr': 'Suggestion basee sur des regles',
            'es': 'Sugerencia basada en reglas',
        }
        return reasons.get(language_code, reasons['en'])

    def _get_option_keep_reason(self, language_code: str) -> str:
        """Return a localized neutral AI reason for keeping an active option."""
        reasons = {
            'en': 'Current configuration appears relevant for this item.',
            'fr': 'La configuration actuelle semble pertinente pour cet article.',
            'es': 'La configuracion actual parece pertinente para este articulo.',
        }
        return reasons.get(language_code, reasons['en'])

    def _extract_price_from_string(self, price_string: str) -> float:
        """
        Extract numeric price from a formatted price string.

        Examples: '+€1.50' -> 1.5, '€2.00' -> 2.0

        Args:
            price_string: Formatted price string

        Returns:
            Float price value
        """
        import re
        match = re.search(r'[\d.]+', price_string.replace(',', '.'))
        if match:
            try:
                return float(match.group())
            except ValueError:
                return 0.0
        return 0.0
