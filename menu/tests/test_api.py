from rest_framework.test import APITestCase
from rest_framework import status
from rest_framework.reverse import reverse
from foodtrucks.tests.factories import FoodTruckFactory
from menu.tests.factories import (
    MenuFactory,
    CategoryFactory,
    ItemFactory,
    OptionGroupFactory,
    OptionFactory,
)


class MenuAPITests(APITestCase):
    def setUp(self):
        self.foodtruck = FoodTruckFactory()
        self.menu = MenuFactory(food_truck=self.foodtruck)

        self.category_pizza = CategoryFactory(menu=self.menu, name='Pizza')
        self.category_drinks = CategoryFactory(menu=self.menu, name='Drinks')

        self.item_margherita = ItemFactory(category=self.category_pizza, name='Margherita', base_price=12.50)
        self.item_pepperoni = ItemFactory(category=self.category_pizza, name='Pepperoni', base_price=13.75)
        self.item_cola = ItemFactory(category=self.category_drinks, name='Cola', base_price=3.25)

        self.size_options = OptionGroupFactory(item=self.item_margherita, name='Size')
        self.size_small = OptionFactory(group=self.size_options, name='Small', price_modifier=0)
        self.size_large = OptionFactory(group=self.size_options, name='Large', price_modifier=2.50)

    def test_retrieve_menu_hierarchy(self):
        url = reverse('menu-detail', kwargs={'pk': self.menu.id})
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['id'], self.menu.id)
        self.assertEqual(response.data['foodtruck'], self.foodtruck.id)
        self.assertEqual(len(response.data['categories']), 2)

        category_names = [category['name'] for category in response.data['categories']]
        self.assertIn('Pizza', category_names)
        self.assertIn('Drinks', category_names)

        margherita = next(cat for cat in response.data['categories'] if cat['name'] == 'Pizza')['items'][0]
        self.assertEqual(margherita['name'], 'Margherita')
        self.assertEqual(len(margherita['option_groups']), 1)
        self.assertEqual(margherita['option_groups'][0]['name'], 'Size')
        self.assertEqual(len(margherita['option_groups'][0]['options']), 2)

    def test_search_menu_items_by_name(self):
        url = reverse('menu-detail', kwargs={'pk': self.menu.id}) + '?item_search=cola'
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['categories']), 1)
        self.assertEqual(response.data['categories'][0]['name'], 'Drinks')

    def test_menu_not_found_for_invalid_id(self):
        url = reverse('menu-detail', kwargs={'pk': 999999})
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
