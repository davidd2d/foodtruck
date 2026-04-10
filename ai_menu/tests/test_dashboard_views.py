from unittest.mock import patch

from django.core.cache import cache
from django.test import Client, TestCase
from django.urls import reverse

from ai_menu.models import AIRecommendation
from foodtrucks.tests.factories import FoodTruckFactory, UserFactory
from menu.models import Category, Combo, Option, OptionGroup
from menu.tests.factories import MenuFactory, CategoryFactory, ItemFactory


class AIMenuDashboardViewsTests(TestCase):
    """Integration tests for the owner AI menu dashboard and AJAX endpoint."""

    def setUp(self):
        self.owner = UserFactory(is_foodtruck_owner=True)
        self.other_user = UserFactory(is_foodtruck_owner=True)
        self.foodtruck = FoodTruckFactory(owner=self.owner, name='Alpha Truck')
        self.menu = MenuFactory(food_truck=self.foodtruck, name='Main Menu')
        self.category = CategoryFactory(menu=self.menu, name='Burgers')
        self.item = ItemFactory(
            category=self.category,
            name='Classic Burger',
            description='Beef patty with pickles',
        )
        self.dashboard_url = reverse('ai_menu:dashboard', kwargs={'slug': self.foodtruck.slug})
        self.analyze_url = reverse('ai_menu:analyze-item', kwargs={'item_id': self.item.id})
        cache.clear()

    def tearDown(self):
        cache.clear()

    def test_owner_can_view_ai_menu_dashboard(self):
        self.client.force_login(self.owner)

        AIRecommendation.objects.create(
            item=self.item,
            recommendation_type='free_option',
            payload={'name': 'Old accepted', 'reason': 'Kept for history'},
            status='accepted',
        )
        AIRecommendation.objects.create(
            item=self.item,
            recommendation_type='bundle',
            payload={'name': 'Old rejected', 'reason': 'Not a fit'},
            status='rejected',
        )

        response = self.client.get(self.dashboard_url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'AI Menu Analysis')
        self.assertContains(response, 'Classic Burger')
        self.assertContains(response, 'Analyze this dish')
        self.assertContains(response, 'Accepted History')
        self.assertContains(response, 'Rejected History')

    def test_non_owner_cannot_view_ai_menu_dashboard(self):
        self.client.force_login(self.other_user)

        response = self.client.get(self.dashboard_url)

        self.assertEqual(response.status_code, 404)

    def test_endpoint_requires_authentication(self):
        response = self.client.post(self.analyze_url)

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()['success'], False)

    def test_owner_can_analyze_item_and_receive_grouped_json(self):
        self.client.force_login(self.owner)

        with patch(
            'ai_menu.services.dashboard.AIRecommendationGeneratorService.generate_and_store_for_item',
            side_effect=self._mock_generation_success,
        ):
            response = self.client.post(self.analyze_url)

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['success'])
        self.assertEqual(len(data['recommendations']['free_options']), 1)
        self.assertEqual(len(data['recommendations']['paid_options']), 1)
        self.assertEqual(len(data['recommendations']['bundles']), 1)
        self.assertIn('Extra pickles', data['html'])
        self.assertEqual(AIRecommendation.objects.for_item(self.item).pending().count(), 3)

    def test_non_owner_cannot_analyze_item(self):
        self.client.force_login(self.other_user)

        response = self.client.post(self.analyze_url)

        self.assertEqual(response.status_code, 404)

    def test_analyze_endpoint_respects_csrf(self):
        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.force_login(self.owner)
        csrf_client.get(self.dashboard_url)
        csrf_token = csrf_client.cookies['csrftoken'].value

        with patch(
            'ai_menu.services.dashboard.AIRecommendationGeneratorService.generate_and_store_for_item',
            side_effect=self._mock_generation_success,
        ):
            response = csrf_client.post(self.analyze_url, HTTP_X_CSRFTOKEN=csrf_token)

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['success'])

    def test_analyze_endpoint_returns_rate_limit_error(self):
        self.client.force_login(self.owner)

        with patch(
            'ai_menu.services.dashboard.AIRecommendationGeneratorService.generate_and_store_for_item',
            side_effect=self._mock_generation_success,
        ):
            first = self.client.post(self.analyze_url)
            second = self.client.post(self.analyze_url)

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 429)
        self.assertEqual(second.json()['success'], False)

    def test_analyze_endpoint_handles_generator_errors(self):
        self.client.force_login(self.owner)

        with patch(
            'ai_menu.services.dashboard.AIRecommendationGeneratorService.generate_and_store_for_item',
            return_value={'status': 'error', 'error': 'OpenAI unavailable', 'recommendations': []},
        ):
            response = self.client.post(self.analyze_url)

        self.assertEqual(response.status_code, 500)
        data = response.json()
        self.assertFalse(data['success'])
        self.assertEqual(data['generation_status'], 'error')
        self.assertIn('Unable to generate AI recommendations', data['message'])

    def test_owner_can_accept_recommendation(self):
        self.client.force_login(self.owner)
        recommendation = AIRecommendation.objects.create(
            item=self.item,
            recommendation_type='free_option',
            payload={'name': 'Extra pickles', 'reason': 'Adds perceived freshness'},
            status='pending',
        )
        url = reverse('ai_menu:recommendation-decision', kwargs={'recommendation_id': recommendation.id})

        response = self.client.post(url, data={'decision': 'accept'})

        self.assertEqual(response.status_code, 200)
        recommendation.refresh_from_db()
        self.assertEqual(recommendation.status, 'accepted')
        self.assertTrue(response.json()['success'])
        self.assertIn('Recommendation accepted', response.json()['message'])
        option_group = OptionGroup.objects.get(item=self.item, name='AI Free Customizations')
        option = Option.objects.get(group=option_group, name='Extra pickles')
        self.assertEqual(str(option.price_modifier), '0.00')

    def test_owner_can_reject_recommendation(self):
        self.client.force_login(self.owner)
        recommendation = AIRecommendation.objects.create(
            item=self.item,
            recommendation_type='bundle',
            payload={'name': 'Burger + Fries combo', 'reason': 'Raises average basket', 'items': ['Burger', 'Fries']},
            status='pending',
        )
        url = reverse('ai_menu:recommendation-decision', kwargs={'recommendation_id': recommendation.id})

        response = self.client.post(url, data={'decision': 'reject'})

        self.assertEqual(response.status_code, 200)
        recommendation.refresh_from_db()
        self.assertEqual(recommendation.status, 'rejected')
        self.assertTrue(response.json()['success'])
        self.assertIn('Recommendation rejected', response.json()['message'])

    def test_accept_paid_recommendation_creates_paid_option(self):
        self.client.force_login(self.owner)
        recommendation = AIRecommendation.objects.create(
            item=self.item,
            recommendation_type='paid_option',
            payload={'name': 'Extra cheddar', 'reason': 'Premium', 'suggested_price': 1.5},
            status='pending',
        )
        url = reverse('ai_menu:recommendation-decision', kwargs={'recommendation_id': recommendation.id})

        response = self.client.post(url, data={'decision': 'accept'})

        self.assertEqual(response.status_code, 200)
        option_group = OptionGroup.objects.get(item=self.item, name='AI Paid Add-ons')
        option = Option.objects.get(group=option_group, name='Extra cheddar')
        self.assertEqual(str(option.price_modifier), '1.50')

    def test_accept_bundle_recommendation_creates_combo(self):
        self.client.force_login(self.owner)
        fries = ItemFactory(category=self.category, name='Fries')
        recommendation = AIRecommendation.objects.create(
            item=self.item,
            recommendation_type='bundle',
            payload={'name': 'Burger + Fries combo', 'reason': 'Raises average basket', 'items': ['Classic Burger', 'Fries']},
            status='pending',
        )
        url = reverse('ai_menu:recommendation-decision', kwargs={'recommendation_id': recommendation.id})

        response = self.client.post(url, data={'decision': 'accept'})

        self.assertEqual(response.status_code, 200)
        combo_category = Category.objects.get(menu=self.menu, name='Combos')
        combo = Combo.objects.get(category=combo_category, name='Burger + Fries combo')
        recommendation.refresh_from_db()
        self.assertEqual(recommendation.payload.get('application_status'), 'applied')
        self.assertEqual(combo.combo_items.count(), 2)
        self.assertTrue(response.json()['success'])

    def test_owner_can_reset_accepted_recommendation_to_pending(self):
        self.client.force_login(self.owner)
        recommendation = AIRecommendation.objects.create(
            item=self.item,
            recommendation_type='free_option',
            payload={
                'name': 'Extra pickles',
                'reason': 'Adds perceived freshness',
                'application': {'group_id': None, 'option_id': None},
                'application_status': 'applied',
                'application_summary': 'Menu option created from AI recommendation.',
            },
            status='pending',
        )
        accept_url = reverse('ai_menu:recommendation-decision', kwargs={'recommendation_id': recommendation.id})
        self.client.post(accept_url, data={'decision': 'accept'})
        recommendation.refresh_from_db()
        option_group = OptionGroup.objects.get(item=self.item, name='AI Free Customizations')
        option = Option.objects.get(group=option_group, name='Extra pickles')
        self.assertEqual(recommendation.status, 'accepted')

        response = self.client.post(accept_url, data={'decision': 'reset'})

        self.assertEqual(response.status_code, 200)
        recommendation.refresh_from_db()
        self.assertEqual(recommendation.status, 'pending')
        self.assertFalse(Option.objects.filter(id=option.id).exists())
        self.assertFalse(OptionGroup.objects.filter(id=option_group.id).exists())

    def test_owner_can_reset_accepted_bundle_to_pending(self):
        self.client.force_login(self.owner)
        ItemFactory(category=self.category, name='Fries')
        recommendation = AIRecommendation.objects.create(
            item=self.item,
            recommendation_type='bundle',
            payload={'name': 'Burger + Fries combo', 'reason': 'Raises average basket', 'items': ['Classic Burger', 'Fries']},
            status='pending',
        )
        decision_url = reverse('ai_menu:recommendation-decision', kwargs={'recommendation_id': recommendation.id})

        self.client.post(decision_url, data={'decision': 'accept'})
        recommendation.refresh_from_db()
        combo_category = Category.objects.get(menu=self.menu, name='Combos')
        combo = Combo.objects.get(category=combo_category, name='Burger + Fries combo')
        self.assertEqual(recommendation.status, 'accepted')

        response = self.client.post(decision_url, data={'decision': 'reset'})

        self.assertEqual(response.status_code, 200)
        recommendation.refresh_from_db()
        self.assertEqual(recommendation.status, 'pending')
        self.assertFalse(Combo.objects.filter(id=combo.id).exists())
        self.assertFalse(Category.objects.filter(id=combo_category.id).exists())

    def test_owner_can_reset_rejected_recommendation_to_pending(self):
        self.client.force_login(self.owner)
        recommendation = AIRecommendation.objects.create(
            item=self.item,
            recommendation_type='bundle',
            payload={'name': 'Burger + Fries combo', 'reason': 'Raises average basket', 'items': ['Burger', 'Fries']},
            status='rejected',
        )
        url = reverse('ai_menu:recommendation-decision', kwargs={'recommendation_id': recommendation.id})

        response = self.client.post(url, data={'decision': 'reset'})

        self.assertEqual(response.status_code, 200)
        recommendation.refresh_from_db()
        self.assertEqual(recommendation.status, 'pending')

    def test_non_owner_cannot_decide_recommendation(self):
        self.client.force_login(self.other_user)
        recommendation = AIRecommendation.objects.create(
            item=self.item,
            recommendation_type='paid_option',
            payload={'name': 'Extra cheddar', 'reason': 'Premium', 'suggested_price': 1.5},
            status='pending',
        )
        url = reverse('ai_menu:recommendation-decision', kwargs={'recommendation_id': recommendation.id})

        response = self.client.post(url, data={'decision': 'accept'})

        self.assertEqual(response.status_code, 404)

    def test_decision_endpoint_rejects_invalid_action(self):
        self.client.force_login(self.owner)
        recommendation = AIRecommendation.objects.create(
            item=self.item,
            recommendation_type='free_option',
            payload={'name': 'Extra pickles', 'reason': 'Adds perceived freshness'},
            status='pending',
        )
        url = reverse('ai_menu:recommendation-decision', kwargs={'recommendation_id': recommendation.id})

        response = self.client.post(url, data={'decision': 'archive'})

        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.json()['success'])

    def test_decision_endpoint_rejects_non_pending_recommendation(self):
        self.client.force_login(self.owner)
        recommendation = AIRecommendation.objects.create(
            item=self.item,
            recommendation_type='free_option',
            payload={'name': 'Extra pickles', 'reason': 'Adds perceived freshness'},
            status='accepted',
        )
        url = reverse('ai_menu:recommendation-decision', kwargs={'recommendation_id': recommendation.id})

        response = self.client.post(url, data={'decision': 'reject'})

        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.json()['success'])

    def test_decision_endpoint_requires_authentication(self):
        recommendation = AIRecommendation.objects.create(
            item=self.item,
            recommendation_type='free_option',
            payload={'name': 'Extra pickles', 'reason': 'Adds perceived freshness'},
            status='pending',
        )
        url = reverse('ai_menu:recommendation-decision', kwargs={'recommendation_id': recommendation.id})

        response = self.client.post(url, data={'decision': 'accept'})

        self.assertEqual(response.status_code, 401)
        self.assertFalse(response.json()['success'])

    def _mock_generation_success(self, item):
        AIRecommendation.objects.create(
            item=item,
            recommendation_type='free_option',
            payload={'name': 'Extra pickles', 'reason': 'Adds perceived freshness'},
            status='pending',
        )
        AIRecommendation.objects.create(
            item=item,
            recommendation_type='paid_option',
            payload={'name': 'Extra cheddar', 'reason': 'Popular premium upgrade', 'suggested_price': 1.5},
            status='pending',
        )
        AIRecommendation.objects.create(
            item=item,
            recommendation_type='bundle',
            payload={'name': 'Burger + Fries combo', 'reason': 'Raises average basket', 'items': ['Burger', 'Fries']},
            status='pending',
        )
        return {
            'status': 'success',
            'recommendations': list(AIRecommendation.objects.for_item(item).values_list('id', flat=True)),
        }