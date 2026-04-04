# Legacy test module. Order subsystem tests have been moved into the orders/tests package.


        # Add item
        order.add_item(self.item, 2)

        # Check order item was created
        order_item = OrderItem.objects.get(order=order)
        self.assertEqual(order_item.item, self.item)
        self.assertEqual(order_item.quantity, 2)
        self.assertEqual(order_item.unit_price, Decimal('12.00'))
        self.assertEqual(order_item.total_price, Decimal('24.00'))

        # Check order total was updated
        order.refresh_from_db()
        self.assertEqual(order.total_price, Decimal('24.00'))

    def test_calculate_total(self):
        """Test calculating order total."""
        order = Order.objects.create(
            customer=self.user,
            food_truck=self.foodtruck,
            pickup_slot=self.pickup_slot
        )

        # Add multiple items
        order.add_item(self.item, 1)  # $12.00
        order.add_item(self.item, 2)  # $24.00

        # Total should be $36.00
        self.assertEqual(order.calculate_total(), Decimal('36.00'))
        self.assertEqual(order.total_price, Decimal('36.00'))

    def test_submit_order(self):
        """Test submitting a valid order."""
        order = Order.objects.create(
            customer=self.user,
            food_truck=self.foodtruck,
            pickup_slot=self.pickup_slot
        )

        # Add item
        order.add_item(self.item, 1)

        # Submit order
        order.submit()

        # Check status changed
        order.refresh_from_db()
        self.assertEqual(order.status, 'submitted')

    def test_cannot_submit_empty_order(self):
        """Test that empty orders cannot be submitted."""
        order = Order.objects.create(
            customer=self.user,
            food_truck=self.foodtruck,
            pickup_slot=self.pickup_slot
        )

        # Try to submit empty order
        with self.assertRaises(ValidationError):
            order.submit()

    def test_cannot_submit_if_slot_full(self):
        """Test that orders cannot be submitted if pickup slot is full."""
        # Fill the slot
        for i in range(5):  # capacity is 5
            user = User.objects.create_user(
                email=f'user{i}@example.com',
                password='password123'
            )
            order = Order.objects.create(
                customer=user,
                food_truck=self.foodtruck,
                pickup_slot=self.pickup_slot
            )
            order.add_item(self.item, 1)
            order.submit()

        # Try to create another order
        new_user = User.objects.create_user(
            email='newuser@example.com',
            password='password123'
        )
        new_order = Order.objects.create(
            customer=new_user,
            food_truck=self.foodtruck,
            pickup_slot=self.pickup_slot
        )
        new_order.add_item(self.item, 1)

        # Should not be able to submit
        with self.assertRaises(ValidationError):
            new_order.submit()

    def test_cannot_modify_after_submit(self):
        """Test that orders cannot be modified after submission."""
        order = Order.objects.create(
            customer=self.user,
            food_truck=self.foodtruck,
            pickup_slot=self.pickup_slot
        )

        # Add item
        order.add_item(self.item, 1)

        # Submit order
        order.submit()

        # Try to add another item
        with self.assertRaises(ValidationError):
            order.add_item(self.item, 1)


class OrderAPITestCase(APITestCase):
    """Test Order API endpoints."""

    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            email='test@example.com',
            password='password123'
        )
        self.plan = Plan.objects.create(
            name='Premium Plan',
            code='premium',
            price=Decimal('29.99'),
            allows_ordering=True
        )
        self.foodtruck = FoodTruck.objects.create(
            owner=self.user,
            name='Test Truck',
            description='Test description',
            latitude=40.7128,
            longitude=-74.0060
        )
        self.subscription = Subscription.objects.create(
            food_truck=self.foodtruck,
            plan=self.plan
        )
        self.pickup_slot = PickupSlot.objects.create(
            food_truck=self.foodtruck,
            start_time=timezone.now() + timedelta(hours=1),
            end_time=timezone.now() + timedelta(hours=2),
            capacity=5
        )
        self.menu = Menu.objects.create(food_truck=self.foodtruck, name='Test Menu')
        self.category = Category.objects.create(menu=self.menu, name='Pizza')
        self.item = Item.objects.create(
            category=self.category,
            name='Margherita',
            description='Classic pizza',
            base_price=Decimal('12.00')
        )

        # Authenticate
        self.client.force_authenticate(user=self.user)

    def test_create_order(self):
        """Test creating an order via API."""
        url = reverse('order-list')
        data = {
            'food_truck': self.foodtruck.id,
            'pickup_slot': self.pickup_slot.id
        }

        response = self.client.post(url, data, format='json')

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['status'], 'draft')
        self.assertEqual(response.data['total_price'], '0.00')
        self.assertEqual(response.data['customer'], self.user.id)

    def test_add_item_to_order(self):
        """Test adding an item to an order via API."""
        # Create order first
        order = Order.objects.create(
            customer=self.user,
            food_truck=self.foodtruck,
            pickup_slot=self.pickup_slot
        )

        url = reverse('order-add-item', kwargs={'pk': order.id})
        data = {
            'item_id': self.item.id,
            'quantity': 2
        }

        response = self.client.post(url, data, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], 'item added')

        # Check order was updated
        order.refresh_from_db()
        self.assertEqual(order.total_price, Decimal('24.00'))
        self.assertEqual(order.items.count(), 1)

    def test_submit_order(self):
        """Test submitting an order via API."""
        # Create order with item
        order = Order.objects.create(
            customer=self.user,
            food_truck=self.foodtruck,
            pickup_slot=self.pickup_slot
        )
        order.add_item(self.item, 1)

        url = reverse('order-submit', kwargs={'pk': order.id})

        response = self.client.post(url, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], 'order submitted')

        # Check order status
        order.refresh_from_db()
        self.assertEqual(order.status, 'submitted')

    def test_cannot_submit_empty_order_api(self):
        """Test that empty orders cannot be submitted via API."""
        order = Order.objects.create(
            customer=self.user,
            food_truck=self.foodtruck,
            pickup_slot=self.pickup_slot
        )

        url = reverse('order-submit', kwargs={'pk': order.id})

        response = self.client.post(url, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', response.data)

    def test_cannot_submit_if_slot_full_api(self):
        """Test that orders cannot be submitted if slot is full via API."""
        # Fill the slot
        for i in range(5):
            user = User.objects.create_user(
                email=f'user{i}@example.com',
                password='password123'
            )
            order = Order.objects.create(
                customer=user,
                food_truck=self.foodtruck,
                pickup_slot=self.pickup_slot
            )
            order.add_item(self.item, 1)
            order.submit()

        # Create new order
        new_order = Order.objects.create(
            customer=self.user,
            food_truck=self.foodtruck,
            pickup_slot=self.pickup_slot
        )
        new_order.add_item(self.item, 1)

        url = reverse('order-submit', kwargs={'pk': new_order.id})

        response = self.client.post(url, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', response.data)

    def test_cannot_modify_after_submit_api(self):
        """Test that orders cannot be modified after submission via API."""
        order = Order.objects.create(
            customer=self.user,
            food_truck=self.foodtruck,
            pickup_slot=self.pickup_slot
        )
        order.add_item(self.item, 1)
        order.submit()

        url = reverse('order-add-item', kwargs={'pk': order.id})
        data = {
            'item_id': self.item.id,
            'quantity': 1
        }

        response = self.client.post(url, data, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', response.data)

    def test_add_item_with_options(self):
        """Test adding an item with options."""
        # Create option group and option
        option_group = OptionGroup.objects.create(
            item=self.item,
            name='Size'
        )
        option = Option.objects.create(
            group=option_group,
            name='Large',
            price_modifier=Decimal('2.00')
        )

        order = Order.objects.create(
            customer=self.user,
            food_truck=self.foodtruck,
            pickup_slot=self.pickup_slot
        )

        url = reverse('order-add-item', kwargs={'pk': order.id})
        data = {
            'item_id': self.item.id,
            'quantity': 1,
            'selected_options': [option.id]
        }

        response = self.client.post(url, data, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Check total includes option price
        order.refresh_from_db()
        self.assertEqual(order.total_price, Decimal('14.00'))  # 12 + 2

    def test_invalid_item_id(self):
        """Test adding item with invalid item_id."""
        order = Order.objects.create(
            customer=self.user,
            food_truck=self.foodtruck,
            pickup_slot=self.pickup_slot
        )

        url = reverse('order-add-item', kwargs={'pk': order.id})
        data = {
            'item_id': 99999,  # Invalid ID
            'quantity': 1
        }

        response = self.client.post(url, data, format='json')

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(response.data['error'], 'Item not found')

    def test_invalid_quantity(self):
        """Test adding item with invalid quantity."""
        order = Order.objects.create(
            customer=self.user,
            food_truck=self.foodtruck,
            pickup_slot=self.pickup_slot
        )

        url = reverse('order-add-item', kwargs={'pk': order.id})
        data = {
            'item_id': self.item.id,
            'quantity': 0  # Invalid quantity
        }

        response = self.client.post(url, data, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('quantity', response.data)
