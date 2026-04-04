from decimal import Decimal
from rest_framework import status
from rest_framework.reverse import reverse
from rest_framework.test import APITestCase
from orders.tests.factories import (
    UserFactory,
    FoodTruckFactory,
    PickupSlotFactory,
    MenuFactory,
    CategoryFactory,
    ItemFactory,
    OptionGroupFactory,
    OptionFactory,
)


class FoodtruckMenuCartIntegrationTests(APITestCase):
    def setUp(self):
        self.user = UserFactory()
        self.foodtruck = FoodTruckFactory(owner=self.user)
        self.menu = MenuFactory(food_truck=self.foodtruck)
        self.category = CategoryFactory(menu=self.menu, name='Burgers')
        self.item = ItemFactory(category=self.category, name='Burger', base_price=Decimal('8.00'))
        self.option_group = OptionGroupFactory(item=self.item, name='Add-ons', min_choices=0, max_choices=2)
        self.cheese = OptionFactory(group=self.option_group, name='Cheese', price_modifier=Decimal('1.50'))
        self.bacon = OptionFactory(group=self.option_group, name='Bacon', price_modifier=Decimal('2.00'))

    def test_fetch_menu_and_add_item_to_cart(self):
        url = reverse('foodtruck-menu', kwargs={'slug': self.foodtruck.slug})
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['foodtruck'], self.foodtruck.slug)
        self.assertEqual(response.data['categories'][0]['name'], 'Burgers')

        add_url = reverse('cart-add')
        payload = {
            'foodtruck_slug': self.foodtruck.slug,
            'item_id': self.item.id,
            'quantity': 2,
            'selected_options': [self.cheese.id, self.bacon.id],
        }

        add_response = self.client.post(add_url, payload, format='json')
        self.assertEqual(add_response.status_code, status.HTTP_200_OK)
        self.assertEqual(add_response.data['item_count'], 2)
        self.assertEqual(add_response.data['total_price'], '23.00')

        cart_url = reverse('cart-detail')
        cart_response = self.client.get(cart_url)
        self.assertEqual(cart_response.status_code, status.HTTP_200_OK)
        self.assertEqual(cart_response.data['item_count'], 2)
        self.assertEqual(cart_response.data['total_price'], '23.00')
        self.assertEqual(cart_response.data['items'][0]['selected_options'][0]['name'], 'Cheese')
