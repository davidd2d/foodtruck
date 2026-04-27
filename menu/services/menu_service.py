from django.http import Http404
from django.shortcuts import get_object_or_404

from foodtrucks.models import FoodTruck
from ..models import Menu


class MenuService:
    """Business logic for menu retrieval and foodtruck menu composition."""

    @staticmethod
    def get_active_menu_for_foodtruck(slug):
        """Return the active menu for a foodtruck slug.

        Raises:
            Http404: if the foodtruck or active menu does not exist.
        """
        foodtruck = get_object_or_404(FoodTruck.objects.filter(is_active=True), slug=slug)

        menu = (
            Menu.objects.filter(food_truck=foodtruck, is_active=True)
            .prefetch_related(
                'categories__items__option_groups__options',
                'categories__items__compatible_preferences',
                'categories__combos__combo_items__item',
                'categories__combos__combo_items__fixed_items',
            )
            .order_by('-created_at')
            .first()
        )

        if menu is None:
            raise Http404(f"No active menu found for foodtruck '{slug}'")

        return menu
