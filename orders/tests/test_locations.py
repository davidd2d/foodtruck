import ssl
from decimal import Decimal
from datetime import time
from unittest.mock import Mock, patch

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from orders.models import Location, ServiceSchedule
from orders.services.location_geocoding_service import LocationGeocodingService
from orders.tests.factories import FoodTruckFactory, UserFactory


class LocationModelTests(TestCase):
    def setUp(self):
        self.user = UserFactory()
        self.foodtruck = FoodTruckFactory(owner=self.user)
        self.schedule = ServiceSchedule.objects.create(
            food_truck=self.foodtruck,
            day_of_week=timezone.localdate().weekday(),
            start_time=time(10, 0),
            end_time=time(11, 0),
            capacity_per_slot=5,
            slot_duration_minutes=15,
        )

    def _create_location(self, **overrides):
        defaults = {
            'food_truck': self.foodtruck,
            'address_line_1': '123 Central Ave',
            'postal_code': '75000',
            'city': 'Paris',
            'country': 'France',
            'latitude': Decimal('48.856600'),
            'longitude': Decimal('2.352200'),
        }
        defaults.update(overrides)
        location = Location(**defaults)
        location.full_clean()
        location.save()
        return location

    def test_location_creation_and_address(self):
        location = self._create_location(address_line_2='Suite 1')
        self.assertIn('Paris', location.get_full_address())
        self.assertEqual(location.get_coordinates(), (48.8566, 2.3522))

    def test_invalid_coordinates_raise_error(self):
        with self.assertRaises(ValidationError):
            self._create_location(latitude=Decimal('91.0000'))

    def test_location_must_share_foodtruck_with_schedule(self):
        other_foodtruck = FoodTruckFactory(owner=self.user, latitude=Decimal('52.52'), longitude=Decimal('13.4050'))
        location = self._create_location(food_truck=other_foodtruck)
        with self.assertRaises(ValidationError):
            self.schedule.full_clean()
            self.schedule.location = location
            self.schedule.clean()

    def test_distance_to_returns_kilometers(self):
        location = self._create_location()
        distance = location.distance_to(48.8566, 2.3622)
        self.assertGreater(distance, 0)
        self.assertAlmostEqual(distance, 0.7, places=1)

    def test_location_same_as_base_location(self):
        quantized_lat = Decimal(self.foodtruck.latitude).quantize(Decimal('0.000001'))
        quantized_lng = Decimal(self.foodtruck.longitude).quantize(Decimal('0.000001'))
        location = self._create_location(
            latitude=quantized_lat,
            longitude=quantized_lng,
        )
        self.assertTrue(location.is_same_as_base_location())
        self.assertFalse(location.is_same_as_base_location() is False)


class ServiceScheduleLocationTests(TestCase):
    def setUp(self):
        self.foodtruck = FoodTruckFactory()
        self.schedule = ServiceSchedule.objects.create(
            food_truck=self.foodtruck,
            day_of_week=timezone.localdate().weekday(),
            start_time=time(9, 0),
            end_time=time(10, 0),
            capacity_per_slot=3,
            slot_duration_minutes=15,
        )

    def _create_location(self, **overrides):
        defaults = {
            'food_truck': self.foodtruck,
            'address_line_1': '1 Rue de Test',
            'postal_code': '75001',
            'city': 'Paris',
            'country': 'France',
            'latitude': Decimal('48.8566'),
            'longitude': Decimal('2.3522'),
        }
        defaults.update(overrides)
        location = Location(**defaults)
        location.full_clean()
        location.save()
        return location

    def test_effective_location_falls_back_to_base(self):
        self.assertEqual(self.schedule.get_effective_location(), self.foodtruck)

    def test_effective_location_uses_custom_location(self):
        location = self._create_location(
            address_line_1='1 Rue de Test',
            postal_code='75001',
            city='Paris',
            country='France',
            latitude=Decimal('48.8566'),
            longitude=Decimal('2.3522'),
        )
        self.schedule.location = location
        self.schedule.full_clean()
        self.schedule.save()
        self.schedule.refresh_from_db()
        self.assertTrue(self.schedule.has_custom_location())
        self.assertNotEqual(self.schedule.get_effective_location(), self.foodtruck)


class FoodTruckLocationHelpersTests(TestCase):
    def setUp(self):
        self.foodtruck = FoodTruckFactory()
        self.schedule = ServiceSchedule.objects.create(
            food_truck=self.foodtruck,
            day_of_week=timezone.localdate().weekday(),
            start_time=time(11, 0),
            end_time=time(12, 0),
            capacity_per_slot=2,
            slot_duration_minutes=15,
        )

    def test_base_coordinates(self):
        lat, lng = self.foodtruck.get_base_coordinates()
        self.assertIsInstance(lat, float)
        self.assertIsInstance(lng, float)

    def test_current_location_for_schedule_targets_effective_location(self):
        base = self.foodtruck.get_current_location_for_schedule(self.schedule)
        self.assertEqual(base, self.foodtruck)


class LocationGeocodingTests(TestCase):
    @patch('orders.services.location_geocoding_service.Nominatim')
    def test_build_geolocator_uses_ssl_context(self, mock_nominatim):
        LocationGeocodingService._build_geolocator()

        self.assertIn('ssl_context', mock_nominatim.call_args.kwargs)

    @patch('orders.services.location_geocoding_service.Nominatim')
    def test_geocode_address_returns_decimal_coordinates(self, mock_nominatim):
        geolocator = mock_nominatim.return_value
        geolocator.geocode.return_value = Mock(latitude=48.8566123, longitude=2.3522219)

        latitude, longitude = LocationGeocodingService.geocode_address('10 Rue de Rivoli, 75001 Paris, France')

        self.assertEqual(latitude, Decimal('48.856612'))
        self.assertEqual(longitude, Decimal('2.352222'))

    @patch('orders.services.location_geocoding_service.Nominatim')
    def test_reverse_geocode_returns_address_parts(self, mock_nominatim):
        geolocator = mock_nominatim.return_value
        geolocator.reverse.return_value = Mock(
            address='10 Rue de Rivoli, 75001 Paris, France',
            raw={
                'address': {
                    'house_number': '10',
                    'road': 'Rue de Rivoli',
                    'postcode': '75001',
                    'city': 'Paris',
                    'country': 'France',
                }
            },
        )

        result = LocationGeocodingService.reverse_geocode(48.8566, 2.3522)

        self.assertEqual(result['address_line_1'], '10 Rue de Rivoli')
        self.assertEqual(result['postal_code'], '75001')
        self.assertEqual(result['city'], 'Paris')
        self.assertEqual(result['country'], 'France')

    @patch('orders.services.location_geocoding_service.Nominatim')
    def test_geocode_address_reports_ssl_error_cleanly(self, mock_nominatim):
        geolocator = mock_nominatim.return_value
        geolocator.geocode.side_effect = ssl.SSLError('CERTIFICATE_VERIFY_FAILED')

        with self.assertRaisesMessage(ValidationError, 'SSL certificate validation failed'):
            LocationGeocodingService.geocode_address('6 rue Parrayon, 59800 Lille, France')

    def test_location_can_resolve_coordinates_from_address(self):
        location = Location(
            food_truck=FoodTruckFactory(),
            address_line_1='10 Rue de Rivoli',
            postal_code='75001',
            city='Paris',
            country='France',
        )

        geocoding_service = Mock()
        geocoding_service.geocode_address.return_value = (Decimal('48.856600'), Decimal('2.352200'))

        location.resolve_geodata(geocoding_service=geocoding_service)

        self.assertEqual(location.latitude, Decimal('48.856600'))
        self.assertEqual(location.longitude, Decimal('2.352200'))

    def test_location_can_resolve_address_from_coordinates(self):
        location = Location(
            food_truck=FoodTruckFactory(),
            postal_code='',
            city='',
            country='',
            latitude=Decimal('48.856600'),
            longitude=Decimal('2.352200'),
        )

        geocoding_service = Mock()
        geocoding_service.reverse_geocode.return_value = {
            'address_line_1': '10 Rue de Rivoli',
            'address_line_2': '',
            'postal_code': '75001',
            'city': 'Paris',
            'country': 'France',
        }

        location.resolve_geodata(geocoding_service=geocoding_service)

        self.assertEqual(location.address_line_1, '10 Rue de Rivoli')
        self.assertEqual(location.postal_code, '75001')
        self.assertEqual(location.city, 'Paris')
        self.assertEqual(location.country, 'France')
