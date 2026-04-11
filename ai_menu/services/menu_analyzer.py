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
    BURGER_KEYWORDS = ['burger', 'hamburger', 'beef', 'boeuf', 'chicken burger', 'patty']
    BOWL_KEYWORDS = ['bowl', 'bol', 'poke', 'buddha bowl', 'rice bowl']
    TACO_KEYWORDS = ['taco', 'tacos', 'wrap', 'burrito']

    FREE_OPTION_SUGGESTIONS = {
        'en': {
            'burger': ['Extra lettuce', 'Extra tomato', 'Grilled onions', 'Pickles'],
            'bowl': ['Extra vegetables', 'Lime juice', 'Extra cilantro'],
            'taco': ['Extra onions', 'Lime wedge', 'Extra cilantro'],
        },
        'fr': {
            'burger': ['Salade en plus', 'Tomates en plus', 'Oignons grilles', 'Cornichons'],
            'bowl': ['Legumes en plus', 'Jus de citron vert', 'Coriandre en plus'],
            'taco': ['Oignons en plus', 'Quartier de citron vert', 'Coriandre en plus'],
        },
        'es': {
            'burger': ['Lechuga extra', 'Tomate extra', 'Cebollas a la plancha', 'Pepinillos'],
            'bowl': ['Verduras extra', 'Jugo de lima', 'Cilantro extra'],
            'taco': ['Cebolla extra', 'Gajo de lima', 'Cilantro extra'],
        },
    }

    PAID_OPTION_SUGGESTIONS = {
        'en': {
            'burger': ['Add extra cheese (+€1.00)', 'Add bacon (+€1.50)', 'Add avocado (+€1.50)', 'Sauce on the side (+€0.50)'],
            'bowl': ['Add extra protein (+€2.00)', 'Add avocado (+€1.50)', 'Add egg (+€0.75)'],
            'taco': ['Add spicy sauce (+€0.50)', 'Add extra meat (+€1.50)', 'Add guacamole (+€1.50)'],
        },
        'fr': {
            'burger': ['Ajouter du fromage (+€1.00)', 'Ajouter du bacon (+€1.50)', 'Ajouter de l\'avocat (+€1.50)', 'Sauce a part (+€0.50)'],
            'bowl': ['Ajouter une proteine (+€2.00)', 'Ajouter de l\'avocat (+€1.50)', 'Ajouter un oeuf (+€0.75)'],
            'taco': ['Ajouter une sauce piquante (+€0.50)', 'Ajouter plus de viande (+€1.50)', 'Ajouter du guacamole (+€1.50)'],
        },
        'es': {
            'burger': ['Agregar queso extra (+€1.00)', 'Agregar bacon (+€1.50)', 'Agregar aguacate (+€1.50)', 'Salsa aparte (+€0.50)'],
            'bowl': ['Agregar proteina extra (+€2.00)', 'Agregar aguacate (+€1.50)', 'Agregar huevo (+€0.75)'],
            'taco': ['Agregar salsa picante (+€0.50)', 'Agregar carne extra (+€1.50)', 'Agregar guacamole (+€1.50)'],
        },
    }

    BUNDLE_SUGGESTIONS = {
        'en': {
            'burger': ['Burger + Fries combo', 'Burger + Drink combo', 'Burger + Side salad combo'],
            'bowl': ['Bowl + Drink combo', 'Bowl + Soup combo'],
            'taco': ['Tacos (3) + Drink combo', 'Tacos (3) + Salsa combo'],
        },
        'fr': {
            'burger': ['Menu burger + frites', 'Menu burger + boisson', 'Menu burger + salade'],
            'bowl': ['Menu bowl + boisson', 'Menu bowl + soupe'],
            'taco': ['Menu 3 tacos + boisson', 'Menu 3 tacos + salsa'],
        },
        'es': {
            'burger': ['Combo hamburguesa + patatas', 'Combo hamburguesa + bebida', 'Combo hamburguesa + ensalada'],
            'bowl': ['Combo bowl + bebida', 'Combo bowl + sopa'],
            'taco': ['Combo 3 tacos + bebida', 'Combo 3 tacos + salsa'],
        },
    }

    @staticmethod
    def analyze_item(item, language_code: str = 'en') -> Dict[str, Any]:
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
        free_options = MenuAnalyzerService._suggest_free_options(detected_category, item_text, language_code)
        paid_options = MenuAnalyzerService._suggest_paid_options(detected_category, item_text, language_code)
        bundles = MenuAnalyzerService._suggest_bundles(detected_category, item_text, language_code)

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
    def _suggest_free_options(category: str, item_text: str, language_code: str) -> List[str]:
        """
        Suggest free (no price modifier) options based on category.

        Args:
            category: Detected category
            item_text: Lowercase combined text

        Returns:
            List of suggestion strings
        """
        return MenuAnalyzerService.FREE_OPTION_SUGGESTIONS.get(
            language_code,
            MenuAnalyzerService.FREE_OPTION_SUGGESTIONS['en'],
        ).get(category, [])

    @staticmethod
    def _suggest_paid_options(category: str, item_text: str, language_code: str) -> List[str]:
        """
        Suggest paid (with price modifier) options based on category.

        Args:
            category: Detected category
            item_text: Lowercase combined text

        Returns:
            List of suggestion strings with estimated price modifiers
        """
        return MenuAnalyzerService.PAID_OPTION_SUGGESTIONS.get(
            language_code,
            MenuAnalyzerService.PAID_OPTION_SUGGESTIONS['en'],
        ).get(category, [])

    @staticmethod
    def _suggest_bundles(category: str, item_text: str, language_code: str) -> List[str]:
        """
        Suggest bundle opportunities based on category.

        Args:
            category: Detected category
            item_text: Lowercase combined text

        Returns:
            List of bundle suggestion strings
        """
        return MenuAnalyzerService.BUNDLE_SUGGESTIONS.get(
            language_code,
            MenuAnalyzerService.BUNDLE_SUGGESTIONS['en'],
        ).get(category, [])
