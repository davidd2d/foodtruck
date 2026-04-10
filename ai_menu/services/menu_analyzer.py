"""
Menu Analyzer Service

Provides rule-based analysis of menu items for AI recommendations.
Designed to be extensible for future LLM integration.
"""

import logging
from typing import Dict, List, Any

logger = logging.getLogger(__name__)


class MenuAnalyzerService:
    """
    Analyzes menu items and generates AI recommendations.

    This MVP implementation uses rule-based analysis. Future versions
    can integrate with external LLM APIs while maintaining the same interface.
    """

    # Rules patterns for different item types
    BURGER_KEYWORDS = ['burger', 'beef', 'chicken burger', 'patty']
    BOWL_KEYWORDS = ['bowl', 'poke', 'buddha bowl', 'rice bowl']
    TACO_KEYWORDS = ['taco', 'tacos', 'wrap']

    @staticmethod
    def analyze_item(item) -> Dict[str, Any]:
        """
        Analyze a menu item and suggest recommendations.

        Args:
            item: Menu Item instance to analyze

        Returns:
            Dict with structure:
            {
                'detected_category': str,
                'free_options_suggestions': List[str],
                'paid_options_suggestions': List[str],
                'bundles_suggestions': List[str],
            }
        """
        item_text = f"{item.name} {item.description}".lower()

        detected_category = MenuAnalyzerService._detect_category(item_text)
        free_options = MenuAnalyzerService._suggest_free_options(detected_category, item_text)
        paid_options = MenuAnalyzerService._suggest_paid_options(detected_category, item_text)
        bundles = MenuAnalyzerService._suggest_bundles(detected_category, item_text)

        return {
            'detected_category': detected_category,
            'free_options_suggestions': free_options,
            'paid_options_suggestions': paid_options,
            'bundles_suggestions': bundles,
        }

    @staticmethod
    def _detect_category(item_text: str) -> str:
        """
        Detect the primary category of an item from its text.

        Args:
            item_text: Lowercase combined name and description

        Returns:
            str: Category name (burger, bowl, taco, or other)
        """
        if any(keyword in item_text for keyword in MenuAnalyzerService.BURGER_KEYWORDS):
            return 'burger'
        elif any(keyword in item_text for keyword in MenuAnalyzerService.BOWL_KEYWORDS):
            return 'bowl'
        elif any(keyword in item_text for keyword in MenuAnalyzerService.TACO_KEYWORDS):
            return 'taco'
        return 'other'

    @staticmethod
    def _suggest_free_options(category: str, item_text: str) -> List[str]:
        """
        Suggest free (no price modifier) options based on category.

        Args:
            category: Detected category
            item_text: Lowercase combined text

        Returns:
            List of suggestion strings
        """
        suggestions = []

        if category == 'burger':
            suggestions = [
                'Extra lettuce',
                'Extra tomato',
                'Grilled onions',
                'Pickles',
            ]
        elif category == 'bowl':
            suggestions = [
                'Extra vegetables',
                'Lime juice',
                'Extra cilantro',
            ]
        elif category == 'taco':
            suggestions = [
                'Extra onions',
                'Lime wedge',
                'Extra cilantro',
            ]

        return suggestions

    @staticmethod
    def _suggest_paid_options(category: str, item_text: str) -> List[str]:
        """
        Suggest paid (with price modifier) options based on category.

        Args:
            category: Detected category
            item_text: Lowercase combined text

        Returns:
            List of suggestion strings with estimated price modifiers
        """
        suggestions = []

        if category == 'burger':
            suggestions = [
                'Add extra cheese (+€1.00)',
                'Add bacon (+€1.50)',
                'Add avocado (+€1.50)',
                'Sauce on the side (+€0.50)',
            ]
        elif category == 'bowl':
            suggestions = [
                'Add extra protein (+€2.00)',
                'Add avocado (+€1.50)',
                'Add egg (+€0.75)',
            ]
        elif category == 'taco':
            suggestions = [
                'Add spicy sauce (+€0.50)',
                'Add extra meat (+€1.50)',
                'Add guacamole (+€1.50)',
            ]

        return suggestions

    @staticmethod
    def _suggest_bundles(category: str, item_text: str) -> List[str]:
        """
        Suggest bundle opportunities based on category.

        Args:
            category: Detected category
            item_text: Lowercase combined text

        Returns:
            List of bundle suggestion strings
        """
        suggestions = []

        if category == 'burger':
            suggestions = [
                'Burger + Fries combo',
                'Burger + Drink combo',
                'Burger + Side salad combo',
            ]
        elif category == 'bowl':
            suggestions = [
                'Bowl + Drink combo',
                'Bowl + Soup combo',
            ]
        elif category == 'taco':
            suggestions = [
                'Tacos (3) + Drink combo',
                'Tacos (3) + Salsa combo',
            ]

        return suggestions
