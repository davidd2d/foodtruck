import logging
from collections import defaultdict

from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.http import Http404
from django.urls import reverse

from ai_menu.models import AIRecommendation
from ai_menu.services.menu_application import AIRecommendationMenuApplicationService
from ai_menu.services.recommendation_generator import AIRecommendationGeneratorService
from menu.services.menu_service import MenuService

logger = logging.getLogger(__name__)


class AIRecommendationRateLimitError(Exception):
    """Raised when an item analysis is triggered too frequently."""


class AIRecommendationDecisionError(Exception):
    """Raised when a dashboard recommendation decision cannot be applied."""


class AIRecommendationDashboardService:
    """Orchestrates owner dashboard AI analysis and UI-friendly serialization."""

    RATE_LIMIT_SECONDS = 30

    def __init__(self, generator_service=None):
        """Initialize the dashboard orchestration service."""
        self.generator_service = generator_service or AIRecommendationGeneratorService()
        self.menu_application_service = AIRecommendationMenuApplicationService()

    def get_dashboard_categories(self, foodtruck):
        """Return active menu categories with grouped pending recommendations attached."""
        try:
            menu = MenuService.get_active_menu_for_foodtruck(foodtruck.slug)
        except Http404:
            return []

        categories = list(menu.categories.all())
        item_ids = []

        for category in categories:
            dashboard_items = list(category.items.all())
            category.dashboard_items = dashboard_items
            item_ids.extend(item.id for item in dashboard_items)

        grouped_map = self.get_grouped_recommendations_map(item_ids)

        for category in categories:
            for item in category.dashboard_items:
                grouped = grouped_map.get(item.id, self.empty_dashboard_recommendations())
                item.ai_recommendations_grouped = grouped
                item.ai_has_recommendations = self.has_recommendations(grouped)

        return categories

    def analyze_item(self, item, actor_id):
        """Generate, persist, and serialize recommendations for dashboard consumption."""
        self._check_rate_limit(item.id, actor_id)

        generation_result = self.generator_service.generate_and_store_for_item(item)
        if generation_result.get('status') == 'error':
            return {
                'success': False,
                'message': 'Unable to generate AI recommendations right now.',
                'generation_status': 'error',
                'fallback_reason': generation_result.get('error', ''),
                'recommendations': self.empty_dashboard_recommendations(),
            }

        grouped = self.get_grouped_recommendations_for_item(item)
        generation_status = generation_result.get('status', 'success')
        response = {
            'success': True,
            'message': self._build_status_message(generation_status),
            'generation_status': generation_status,
            'fallback_reason': generation_result.get('fallback_reason', ''),
            'recommendations': grouped,
        }

        logger.info(
            'Owner dashboard AI analysis completed for item %s with status %s',
            item.id,
            generation_status,
        )

        return response

    def apply_decision(self, recommendation, decision):
        """Apply an owner decision to a pending recommendation and return refreshed item data."""
        if decision not in {'accept', 'reject', 'reset'}:
            raise AIRecommendationDecisionError('Unsupported recommendation action.')

        try:
            if decision == 'accept':
                metadata = self.menu_application_service.apply_recommendation(recommendation)
                self._merge_application_metadata(recommendation, metadata)
                recommendation.accept()
                message = self._build_decision_message('accepted', metadata)
            elif decision == 'reset':
                metadata = self.menu_application_service.revert_recommendation(recommendation)
                self._clear_application_metadata(recommendation)
                recommendation.reset_to_pending()
                message = 'Recommendation moved back to pending.'
            else:
                recommendation.reject()
                message = 'Recommendation rejected.'
        except ValidationError as exc:
            raise AIRecommendationDecisionError(str(exc)) from exc

        item = recommendation.item
        grouped = self.get_grouped_recommendations_for_item(item)
        return {
            'success': True,
            'message': message,
            'generation_status': 'success',
            'fallback_reason': '',
            'recommendations': grouped,
        }

    def get_grouped_recommendations_for_item(self, item):
        """Return grouped dashboard recommendations for a single item."""
        recommendations = (
            AIRecommendation.objects.for_item(item)
            .order_by('status', 'recommendation_type', 'created_at')
        )
        return self.serialize_recommendations(recommendations)

    def get_grouped_recommendations_map(self, item_ids):
        """Return grouped pending recommendations indexed by item id."""
        if not item_ids:
            return {}

        recommendations = (
            AIRecommendation.objects
            .filter(status__in=['pending', 'accepted', 'rejected'])
            .filter(item_id__in=item_ids)
            .select_related('item')
            .order_by('item_id', 'status', 'recommendation_type', 'created_at')
        )

        grouped_map = {}
        bucket = defaultdict(list)
        for recommendation in recommendations:
            bucket[recommendation.item_id].append(recommendation)

        for item_id, item_recommendations in bucket.items():
            grouped_map[item_id] = self.serialize_recommendations(item_recommendations)

        return grouped_map

    def serialize_recommendations(self, recommendations):
        """Serialize recommendations into UI groups."""
        grouped = self.empty_dashboard_recommendations()

        for recommendation in recommendations:
            payload = recommendation.payload or {}
            serialized = self._serialize_recommendation(recommendation, payload)

            if recommendation.status == 'accepted':
                grouped['history']['accepted'].append(serialized)
                continue

            if recommendation.status == 'rejected':
                grouped['history']['rejected'].append(serialized)
                continue

            if recommendation.recommendation_type == 'free_option':
                grouped['free_options'].append(serialized)
            elif recommendation.recommendation_type == 'paid_option':
                grouped['paid_options'].append(serialized)
            elif recommendation.recommendation_type == 'bundle':
                grouped['bundles'].append(serialized)

        return grouped

    def empty_grouped_recommendations(self):
        """Backward-compatible pending-only structure used by endpoint fallbacks."""
        return {
            'free_options': [],
            'paid_options': [],
            'bundles': [],
        }

    def empty_dashboard_recommendations(self):
        """Return the full dashboard recommendation structure."""
        grouped = self.empty_grouped_recommendations()
        grouped['history'] = {
            'accepted': [],
            'rejected': [],
        }
        return grouped

    def has_recommendations(self, grouped):
        """Return whether any UI group contains recommendations."""
        if any(grouped.get(key) for key in ('free_options', 'paid_options', 'bundles')):
            return True
        history = grouped.get('history', {})
        return bool(history.get('accepted') or history.get('rejected'))

    def _build_status_message(self, generation_status):
        """Return a UI-friendly status message."""
        if generation_status == 'fallback':
            return 'AI was unavailable, so rule-based recommendations were generated.'
        return 'AI analysis completed successfully.'

    def _check_rate_limit(self, item_id, actor_id):
        """Apply a small cooldown per owner and item to reduce abusive triggering."""
        cache_key = f'ai-menu-analysis:{actor_id}:{item_id}'
        if not cache.add(cache_key, '1', timeout=self.RATE_LIMIT_SECONDS):
            raise AIRecommendationRateLimitError(
                'Please wait a few seconds before launching another analysis for this item.'
            )

    def _serialize_recommendation(self, recommendation, payload):
        """Serialize one recommendation for dashboard rendering."""
        application = payload.get('application') or {}
        combo_edit_url = ''
        if application.get('combo_id'):
            combo_edit_url = reverse(
                'ai_menu:combo-edit',
                kwargs={
                    'slug': recommendation.item.category.menu.food_truck.slug,
                    'combo_id': application['combo_id'],
                },
            )
        return {
            'id': recommendation.id,
            'name': payload.get('name', ''),
            'reason': payload.get('reason', ''),
            'suggested_price': payload.get('suggested_price'),
            'items': payload.get('items', []),
            'status': recommendation.status,
            'type': recommendation.recommendation_type,
            'type_label': recommendation.get_recommendation_type_display(),
            'decision_url': f'/dashboard/ai-recommendations/{recommendation.id}/decision/',
            'application_status': payload.get('application_status', ''),
            'application_summary': payload.get('application_summary', ''),
            'application_group_name': application.get('group_name', ''),
            'application_option_name': application.get('option_name', ''),
            'application_combo_name': application.get('combo_name', ''),
            'combo_edit_url': combo_edit_url,
        }

    def _merge_application_metadata(self, recommendation, metadata):
        """Persist application metadata on the recommendation payload."""
        payload = dict(recommendation.payload or {})
        payload.update(metadata)
        recommendation.payload = payload
        recommendation.save(update_fields=['payload', 'updated_at'])

    def _clear_application_metadata(self, recommendation):
        """Remove persisted application metadata when resetting to pending."""
        payload = dict(recommendation.payload or {})
        payload.pop('application', None)
        payload.pop('application_status', None)
        payload.pop('application_summary', None)
        recommendation.payload = payload
        recommendation.save(update_fields=['payload', 'updated_at'])

    def _build_decision_message(self, base_message, metadata):
        """Return a richer success message after applying a decision."""
        summary = metadata.get('application_summary')
        if summary:
            return f'Recommendation {base_message}. {summary}'
        return f'Recommendation {base_message}.'