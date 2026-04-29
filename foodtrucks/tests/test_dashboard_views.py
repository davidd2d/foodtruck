from decimal import Decimal

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

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
        self.assertEqual(payload['completion_rate'], 100.0)

    def test_dashboard_page_renders_foodtruck_navbar(self):
        self.client.force_login(self.owner)

        url = reverse('foodtrucks:foodtruck-dashboard', kwargs={'slug': self.foodtruck.slug})
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'foodtruck-order-navbar')
        self.assertContains(response, 'id="foodtruck-title"')
        self.assertContains(response, 'id="dashboard-clear-category-filter"')

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
            item=self.item_a,
            name='Extras',
            required=False,
        )
        option = Option.objects.create(
            group=option_group,
            name='Extra sauce',
            price_modifier=Decimal('2.00'),
        )
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
