from datetime import timedelta
from decimal import Decimal

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from analytics.models import Event
from foodtrucks.tests.factories import CategoryFactory, FoodTruckFactory, ItemFactory, MenuFactory, UserFactory
from menu.models import Option, OptionGroup
from orders.models import OrderItem, OrderItemOption
from orders.tests.factories import OrderFactory, PickupSlotFactory


class FoodTruckDashboardViewTests(TestCase):
    def setUp(self):
        self.owner = UserFactory()
        self.other_user = UserFactory()
        self.foodtruck = FoodTruckFactory(owner=self.owner)
        self.other_foodtruck = FoodTruckFactory(owner=self.other_user)
        self.menu = MenuFactory(food_truck=self.foodtruck)
        self.category_a = CategoryFactory(menu=self.menu, name='Pasta')
        self.category_b = CategoryFactory(menu=self.menu, name='Desserts', display_order=1)
        self.item_a = ItemFactory(category=self.category_a, name='Pasta Box')
        self.item_b = ItemFactory(category=self.category_b, name='Tiramisu')

        slot = PickupSlotFactory(food_truck=self.foodtruck)
        paid_order = OrderFactory(
            user=self.owner,
            food_truck=self.foodtruck,
            pickup_slot=slot,
            status='completed',
        )
        OrderItem.objects.create(
            order=paid_order,
            item=self.item_a,
            quantity=1,
            unit_price=Decimal('24.00'),
            tax_rate=Decimal('0.0000'),
            total_price=Decimal('24.00'),
        )
        paid_order.total_amount = Decimal('24.00')
        paid_order.total_price = Decimal('24.00')
        paid_order.paid_at = timezone.now()
        paid_order.save(update_fields=['total_amount', 'total_price', 'paid_at'])

    def _dashboard_urls(self, slug):
        return [
            reverse('foodtrucks:foodtruck-dashboard', kwargs={'slug': slug}),
            reverse('foodtrucks:foodtruck-business-intelligence', kwargs={'slug': slug}),
            reverse('foodtrucks:foodtruck-options-analysis', kwargs={'slug': slug}),
            reverse('foodtrucks:foodtruck-dashboard-kpis', kwargs={'slug': slug}),
            reverse('foodtrucks:foodtruck-dashboard-revenue', kwargs={'slug': slug}),
            reverse('foodtrucks:foodtruck-dashboard-orders', kwargs={'slug': slug}),
            reverse('foodtrucks:foodtruck-dashboard-menu-performance', kwargs={'slug': slug}),
            reverse('foodtrucks:foodtruck-dashboard-menu-categories', kwargs={'slug': slug}),
            reverse('foodtrucks:foodtruck-dashboard-slots', kwargs={'slug': slug}),
            reverse('foodtrucks:foodtruck-dashboard-slots-utilization', kwargs={'slug': slug}),
            reverse('foodtrucks:foodtruck-dashboard-slots-revenue', kwargs={'slug': slug}),
            reverse('foodtrucks:foodtruck-dashboard-slots-hourly', kwargs={'slug': slug}),
            reverse('foodtrucks:foodtruck-dashboard-slots-heatmap', kwargs={'slug': slug}),
            reverse('foodtrucks:foodtruck-dashboard-slots-insights', kwargs={'slug': slug}),
            reverse('foodtrucks:foodtruck-dashboard-slots-recommendations', kwargs={'slug': slug}),
            reverse('foodtrucks:foodtruck-dashboard-options', kwargs={'slug': slug}),
            reverse('foodtrucks:foodtruck-dashboard-bi', kwargs={'slug': slug}),
        ]

    def test_owner_can_access_dashboard_pages_and_endpoints(self):
        self.client.force_login(self.owner)

        for url in self._dashboard_urls(self.foodtruck.slug):
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 200)

    def test_non_owner_cannot_access_other_foodtruck_dashboard(self):
        self.client.force_login(self.other_user)

        for url in self._dashboard_urls(self.foodtruck.slug):
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 404)

    def test_anonymous_user_is_redirected_to_login(self):
        for url in self._dashboard_urls(self.foodtruck.slug):
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 302)

    def test_kpis_endpoint_returns_paid_order_data(self):
        self.client.force_login(self.owner)

        url = reverse('foodtrucks:foodtruck-dashboard-kpis', kwargs={'slug': self.foodtruck.slug})
        response = self.client.get(url, {'range': '30d'})

        self.assertEqual(response.status_code, 200)
        payload = response.json()['data']
        self.assertEqual(payload['total_orders'], 1)
        self.assertEqual(payload['total_revenue'], 24.0)
        self.assertEqual(payload['average_order_value'], 24.0)
        self.assertIn('options_revenue_pct', payload)
        self.assertEqual(payload['completion_rate'], 100.0)

    def test_dashboard_page_renders_foodtruck_navbar(self):
        self.client.force_login(self.owner)

        url = reverse('foodtrucks:foodtruck-dashboard', kwargs={'slug': self.foodtruck.slug})
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'foodtruck-order-navbar')
        self.assertContains(response, 'id="foodtruck-title"')
        self.assertContains(response, 'id="dashboard-clear-category-filter"')

    def test_business_intelligence_page_renders(self):
        self.client.force_login(self.owner)

        url = reverse('foodtrucks:foodtruck-business-intelligence', kwargs={'slug': self.foodtruck.slug})
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="foodtruck-bi-page"')
        self.assertContains(response, 'AI Business Intelligence')
        self.assertContains(response, 'id="dashboard-bi-target-form"')
        self.assertContains(response, 'id="bi-target-period"')
        self.assertContains(response, 'name="keywords"')
        self.assertContains(response, 'id="bi-target-loading"')
        self.assertContains(response, 'id="bi-target-feedback"')

    def test_bi_endpoint_can_filter_event_opportunities(self):
        self.client.force_login(self.owner)

        today = timezone.localdate()
        Event.objects.create(
            name='Morning Festival Downtown',
            latitude=self.foodtruck.latitude,
            longitude=self.foodtruck.longitude,
            start_date=today + timedelta(days=2),
            end_date=today + timedelta(days=2),
            expected_attendance=8000,
        )
        Event.objects.create(
            name='Evening Concert Arena',
            latitude=self.foodtruck.latitude,
            longitude=self.foodtruck.longitude,
            start_date=today + timedelta(days=3),
            end_date=today + timedelta(days=3),
            expected_attendance=9000,
        )

        url = reverse('foodtrucks:foodtruck-dashboard-bi', kwargs={'slug': self.foodtruck.slug})
        response = self.client.get(
            url,
            {
                'horizon_days': '30',
                'min_attendance': '1000',
                'period': 'morning',
                'keywords': 'festival',
                'limit': '3',
            },
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn('filters', payload)
        self.assertIn('search_feedback', payload)
        self.assertEqual(payload['filters']['horizon_days'], 30)
        self.assertEqual(payload['filters']['min_attendance'], 1000)
        self.assertEqual(payload['filters']['period'], 'morning')
        self.assertEqual(payload['filters']['keywords'], ['festival'])
        self.assertEqual(payload['filters']['limit'], 3)
        self.assertEqual(len(payload['data']['event_opportunities']), 1)
        self.assertEqual(payload['data']['event_opportunities'][0]['event_name'], 'Morning Festival Downtown')
        self.assertGreaterEqual(payload['search_feedback']['analyzed_events_count'], 1)
        self.assertEqual(payload['search_feedback']['retained_events_count'], 1)

    def test_bi_endpoint_returns_empty_reasons_when_no_result(self):
        self.client.force_login(self.owner)

        today = timezone.localdate()
        Event.objects.create(
            name='Morning Community Market',
            latitude=self.foodtruck.latitude,
            longitude=self.foodtruck.longitude,
            start_date=today + timedelta(days=2),
            end_date=today + timedelta(days=2),
            expected_attendance=300,
        )

        url = reverse('foodtrucks:foodtruck-dashboard-bi', kwargs={'slug': self.foodtruck.slug})
        response = self.client.get(
            url,
            {
                'horizon_days': '7',
                'min_attendance': '10000',
                'min_score': '90',
                'period': 'evening',
                'keywords': 'festival,concert',
                'limit': '5',
            },
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload['search_feedback']['retained_events_count'], 0)
        self.assertIsInstance(payload['search_feedback']['empty_reasons'], list)
        self.assertGreater(len(payload['search_feedback']['empty_reasons']), 0)

    def test_bi_endpoint_radius_filter_excludes_far_events(self):
        """Events outside the radius must be excluded; events inside must be retained."""
        self.client.force_login(self.owner)

        today = timezone.localdate()
        # Place food truck at a known position
        ft_lat = float(self.foodtruck.latitude)
        ft_lng = float(self.foodtruck.longitude)

        # Event very close (~0 km)
        Event.objects.create(
            name='Nearby Festival',
            latitude=ft_lat,
            longitude=ft_lng,
            start_date=today + timedelta(days=2),
            end_date=today + timedelta(days=2),
            expected_attendance=500,
        )
        # Event far away (~200 km north)
        Event.objects.create(
            name='Far Away Concert',
            latitude=ft_lat + 1.8,
            longitude=ft_lng,
            start_date=today + timedelta(days=2),
            end_date=today + timedelta(days=2),
            expected_attendance=500,
        )

        url = reverse('foodtrucks:foodtruck-dashboard-bi', kwargs={'slug': self.foodtruck.slug})
        response = self.client.get(url, {
            'horizon_days': '30',
            'radius_km': '50',
            'limit': '10',
        })

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn('radius_km', payload['filters'])
        self.assertEqual(payload['filters']['radius_km'], 50.0)

        # The trace must include a radius step
        trace_steps = [s['step'] for s in payload['search_feedback']['filter_trace']]
        self.assertIn('radius', trace_steps)

        # Total events in DB should be reported
        self.assertIn('total_events_in_db', payload['search_feedback'])

        # Only the nearby event should pass the radius filter (check via trace counts)
        radius_step = next(s for s in payload['search_feedback']['filter_trace'] if s['step'] == 'radius')
        self.assertEqual(radius_step['count'], 1)

    def test_kpis_endpoint_can_filter_by_category(self):
        self.client.force_login(self.owner)

        slot = PickupSlotFactory(food_truck=self.foodtruck)
        paid_order = OrderFactory(
            user=self.owner,
            food_truck=self.foodtruck,
            pickup_slot=slot,
            status='completed',
        )
        OrderItem.objects.create(
            order=paid_order,
            item=self.item_b,
            quantity=1,
            unit_price=Decimal('10.00'),
            tax_rate=Decimal('0.0000'),
            total_price=Decimal('10.00'),
        )
        paid_order.total_amount = Decimal('10.00')
        paid_order.total_price = Decimal('10.00')
        paid_order.paid_at = timezone.now()
        paid_order.save(update_fields=['total_amount', 'total_price', 'paid_at'])

        url = reverse('foodtrucks:foodtruck-dashboard-kpis', kwargs={'slug': self.foodtruck.slug})
        response = self.client.get(url, {'range': '30d', 'category_id': str(self.category_a.id)})

        self.assertEqual(response.status_code, 200)
        payload = response.json()['data']
        self.assertEqual(payload['total_orders'], 1)
        self.assertEqual(payload['total_revenue'], 24.0)

    def test_option_performance_endpoint_returns_data(self):
        self.client.force_login(self.owner)

        order_item = OrderItem.objects.filter(order__food_truck=self.foodtruck).first()
        option_group = OptionGroup.objects.create(
            category=self.category_a,
            name='Extras',
            required=False,
        )
        option = Option.objects.create(
            group=option_group,
            name='Extra sauce',
            price_modifier=Decimal('2.00'),
        )
        option.items.add(self.item_a)
        OrderItemOption.objects.create(
            order_item=order_item,
            option=option,
            price_modifier=Decimal('2.00'),
        )

        url = reverse('foodtrucks:foodtruck-dashboard-options', kwargs={'slug': self.foodtruck.slug})
        response = self.client.get(url, {'range': '30d'})

        self.assertEqual(response.status_code, 200)
        payload = response.json()['data']
        self.assertIn('top_options', payload)
        self.assertIn('orders_with_options_pct', payload)
        self.assertIn('total_option_revenue', payload)
        self.assertIn('avg_option_revenue_per_order', payload)
        self.assertEqual(len(payload['top_options']), 1)
        self.assertEqual(payload['top_options'][0]['option_name'], 'Extra sauce')
        self.assertEqual(payload['top_options'][0]['selection_count'], 1)
        self.assertAlmostEqual(payload['top_options'][0]['total_revenue'], 2.0)

    def test_option_performance_endpoint_non_owner_returns_404(self):
        self.client.force_login(self.other_user)

        url = reverse('foodtrucks:foodtruck-dashboard-options', kwargs={'slug': self.foodtruck.slug})
        response = self.client.get(url)

        self.assertEqual(response.status_code, 404)

    def test_bi_endpoint_returns_structured_payload_for_owner(self):
        self.client.force_login(self.owner)

        url = reverse('foodtrucks:foodtruck-dashboard-bi', kwargs={'slug': self.foodtruck.slug})
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn('date', payload)
        self.assertIn('data', payload)
        self.assertIn('best_spots', payload['data'])
        self.assertIn('pricing_suggestions', payload['data'])
        self.assertIn('event_opportunities', payload['data'])
        self.assertIn('revenue_prediction', payload['data'])

    def test_bi_endpoint_non_owner_returns_404(self):
        self.client.force_login(self.other_user)

        url = reverse('foodtrucks:foodtruck-dashboard-bi', kwargs={'slug': self.foodtruck.slug})
        response = self.client.get(url)

        self.assertEqual(response.status_code, 404)
