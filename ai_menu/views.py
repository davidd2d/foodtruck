from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.views.decorators.http import require_POST

from ai_menu.forms import ComboItemFormSet, ComboOwnerForm
from ai_menu.models import AIRecommendation
from ai_menu.services.dashboard import (
    AIRecommendationDecisionError,
    AIRecommendationDashboardService,
    AIRecommendationRateLimitError,
)
from foodtrucks.models import FoodTruck
from menu.models import Combo, Item
from menu.services.menu_service import MenuService


@login_required
def dashboard(request, slug):
    """Render the owner-facing AI menu dashboard for one food truck."""
    foodtruck = _get_owner_foodtruck(request.user, slug)
    service = AIRecommendationDashboardService()
    categories = service.get_dashboard_categories(foodtruck)

    return render(request, 'ai_menu/dashboard.html', {
        'foodtruck': foodtruck,
        'categories': categories,
    })


@login_required
def combo_list(request, slug):
    """Render the owner combo management list for one food truck."""
    foodtruck = _get_owner_foodtruck(request.user, slug)
    combos = Combo.objects.filter(
        category__menu__food_truck=foodtruck,
    ).select_related('category').prefetch_related('combo_items__item').order_by('category__display_order', 'display_order', 'name')

    return render(request, 'ai_menu/combo_list.html', {
        'foodtruck': foodtruck,
        'categories': _get_menu_categories(foodtruck),
        'combos': combos,
    })


@login_required
def combo_edit(request, slug, combo_id):
    """Allow a food truck owner to edit a generated combo and its components."""
    foodtruck = _get_owner_foodtruck(request.user, slug)
    combo = get_object_or_404(
        Combo.objects.select_related('category__menu__food_truck').prefetch_related('combo_items'),
        pk=combo_id,
        category__menu__food_truck=foodtruck,
    )
    available_items = Item.objects.filter(
        category__menu__food_truck=foodtruck,
    ).select_related('category').order_by('category__display_order', 'display_order', 'name')

    if request.method == 'POST':
        form = ComboOwnerForm(request.POST, instance=combo)
        formset = ComboItemFormSet(request.POST, instance=combo, available_items=available_items, prefix='combo_items')
        if form.is_valid() and formset.is_valid():
            form.save()
            formset.save()
            messages.success(request, 'Combo updated successfully.')
            return redirect('ai_menu:combo-edit', slug=foodtruck.slug, combo_id=combo.id)
    else:
        form = ComboOwnerForm(instance=combo)
        formset = ComboItemFormSet(instance=combo, available_items=available_items, prefix='combo_items')

    return render(request, 'ai_menu/combo_form.html', {
        'foodtruck': foodtruck,
        'categories': _get_menu_categories(foodtruck),
        'combo': combo,
        'form': form,
        'formset': formset,
    })


@require_POST
def analyze_item(request, item_id):
    """Launch AI analysis for an item and return grouped recommendations as JSON."""
    if not request.user.is_authenticated:
        return JsonResponse({
            'success': False,
            'message': 'Authentication required.',
        }, status=401)

    item = get_object_or_404(
        Item.objects.select_related('category__menu__food_truck'),
        pk=item_id,
        category__menu__food_truck__owner=request.user,
        category__menu__food_truck__is_active=True,
    )

    service = AIRecommendationDashboardService()
    try:
        payload = service.analyze_item(item, actor_id=request.user.id)
    except AIRecommendationRateLimitError as exc:
        return JsonResponse({
            'success': False,
            'message': str(exc),
        }, status=429)

    html = render_to_string('ai_menu/partials/recommendations_panel.html', {
        'item': item,
        'recommendations': payload['recommendations'],
        'message': payload.get('message', ''),
        'generation_status': payload.get('generation_status', 'success'),
        'fallback_reason': payload.get('fallback_reason', ''),
    }, request=request)

    status_code = 200 if payload.get('success') else 500
    return JsonResponse({
        'success': payload.get('success', False),
        'message': payload.get('message', ''),
        'generation_status': payload.get('generation_status', 'error'),
        'fallback_reason': payload.get('fallback_reason', ''),
        'recommendations': payload.get('recommendations', service.empty_grouped_recommendations()),
        'html': html,
    }, status=status_code)


@require_POST
def recommendation_decision(request, recommendation_id):
    """Accept or reject a pending recommendation and return the refreshed item panel."""
    if not request.user.is_authenticated:
        return JsonResponse({
            'success': False,
            'message': 'Authentication required.',
        }, status=401)

    recommendation = get_object_or_404(
        AIRecommendation.objects.select_related('item__category__menu__food_truck'),
        pk=recommendation_id,
        item__category__menu__food_truck__owner=request.user,
        item__category__menu__food_truck__is_active=True,
    )
    decision = request.POST.get('decision', '').strip().lower()

    service = AIRecommendationDashboardService()
    try:
        payload = service.apply_decision(recommendation, decision)
    except AIRecommendationDecisionError as exc:
        return JsonResponse({
            'success': False,
            'message': str(exc),
        }, status=400)

    html = render_to_string('ai_menu/partials/recommendations_panel.html', {
        'item': recommendation.item,
        'recommendations': payload['recommendations'],
        'message': payload.get('message', ''),
        'generation_status': payload.get('generation_status', 'success'),
        'fallback_reason': payload.get('fallback_reason', ''),
    }, request=request)

    return JsonResponse({
        'success': True,
        'message': payload.get('message', ''),
        'generation_status': payload.get('generation_status', 'success'),
        'recommendations': payload.get('recommendations', service.empty_grouped_recommendations()),
        'html': html,
    })


def _get_owner_foodtruck(user, slug):
    return get_object_or_404(
        FoodTruck.objects.prefetch_related('supported_preferences'),
        slug=slug,
        owner=user,
        is_active=True,
    )


def _get_menu_categories(foodtruck):
    try:
        menu = MenuService.get_active_menu_for_foodtruck(foodtruck.slug)
    except Http404:
        return []
    return menu.categories.order_by('display_order', 'name')