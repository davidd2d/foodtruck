import ssl
from decimal import Decimal, ROUND_HALF_UP

import certifi
from django.conf import settings
from django.core.exceptions import ValidationError

from geopy.exc import GeocoderServiceError, GeocoderTimedOut, GeocoderUnavailable
from geopy.geocoders import Nominatim


class LocationGeocodingService:
    """Resolve food truck locations between address data and GPS coordinates."""

    @classmethod
    def _build_ssl_context(cls):
        cafile = getattr(settings, 'GEOCODING_CA_BUNDLE', None) or certifi.where()
        return ssl.create_default_context(cafile=cafile)

    @classmethod
    def _build_geolocator(cls):
        user_agent = getattr(settings, 'GEOCODING_USER_AGENT', 'foodtruck-saas-location-geocoder')
        timeout = getattr(settings, 'GEOCODING_TIMEOUT', 5)
        return Nominatim(
            user_agent=user_agent,
            timeout=timeout,
            ssl_context=cls._build_ssl_context(),
        )

    @staticmethod
    def _raise_ssl_validation_error(exc):
        raise ValidationError(
            'Unable to contact the geocoding service because SSL certificate validation failed. '
            'Check the local CA bundle or configure GEOCODING_CA_BUNDLE.'
        ) from exc

    @staticmethod
    def _to_decimal(value):
        return Decimal(str(value)).quantize(Decimal('0.000001'), rounding=ROUND_HALF_UP)

    @classmethod
    def geocode_address(cls, address):
        if not address:
            raise ValidationError('Address is required to resolve GPS coordinates.')

        try:
            result = cls._build_geolocator().geocode(address)
        except (ssl.SSLCertVerificationError, ssl.SSLError) as exc:
            cls._raise_ssl_validation_error(exc)
        except (GeocoderTimedOut, GeocoderUnavailable, GeocoderServiceError) as exc:
            raise ValidationError(f'Unable to resolve GPS coordinates from this address: {exc}')

        if result is None:
            raise ValidationError('Unable to resolve GPS coordinates from this address.')

        return cls._to_decimal(result.latitude), cls._to_decimal(result.longitude)

    @classmethod
    def reverse_geocode(cls, latitude, longitude):
        try:
            result = cls._build_geolocator().reverse((latitude, longitude), exactly_one=True, language='en')
        except (ssl.SSLCertVerificationError, ssl.SSLError) as exc:
            cls._raise_ssl_validation_error(exc)
        except (GeocoderTimedOut, GeocoderUnavailable, GeocoderServiceError) as exc:
            raise ValidationError(f'Unable to resolve an address from these GPS coordinates: {exc}')

        if result is None:
            raise ValidationError('Unable to resolve an address from these GPS coordinates.')

        address = result.raw.get('address', {})
        city = address.get('city') or address.get('town') or address.get('village') or address.get('municipality') or ''
        road = address.get('road') or address.get('pedestrian') or address.get('footway') or ''
        house_number = address.get('house_number') or ''
        line_1 = ' '.join(part for part in [house_number, road] if part).strip()
        if not line_1:
            line_1 = result.address.split(',')[0].strip()

        return {
            'address_line_1': line_1,
            'address_line_2': '',
            'postal_code': address.get('postcode', ''),
            'city': city,
            'country': address.get('country', ''),
        }