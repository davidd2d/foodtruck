import stripe

from django.conf import settings
from django.core.exceptions import ValidationError

from foodtrucks.models import FoodTruck


class StripeConnectService:
    """Manage seller onboarding and account state synchronization for Stripe Connect."""

    @staticmethod
    def _get_api_key():
        api_key = getattr(settings, 'STRIPE_SECRET_KEY', None)
        if not api_key:
            raise ValidationError('STRIPE_SECRET_KEY is not configured.')
        stripe.api_key = api_key
        return api_key

    @classmethod
    def ensure_connected_account(cls, food_truck):
        cls._get_api_key()

        if food_truck.stripe_connect_account_id:
            return food_truck.stripe_connect_account_id

        account = stripe.Account.create(
            type='express',
            country=getattr(settings, 'STRIPE_CONNECT_DEFAULT_COUNTRY', 'FR'),
            email=food_truck.owner.email,
            metadata={'food_truck_id': str(food_truck.id), 'food_truck_slug': food_truck.slug},
            business_profile={'name': food_truck.name},
        )
        food_truck.stripe_connect_account_id = account['id']
        food_truck.save(update_fields=['stripe_connect_account_id'])
        return food_truck.stripe_connect_account_id

    @classmethod
    def create_onboarding_link(cls, food_truck, *, refresh_url, return_url):
        account_id = cls.ensure_connected_account(food_truck)
        account_link = stripe.AccountLink.create(
            account=account_id,
            refresh_url=refresh_url,
            return_url=return_url,
            type='account_onboarding',
        )
        return account_link['url']

    @staticmethod
    def sync_account_state(food_truck, account):
        details_submitted = bool(account.get('details_submitted'))
        charges_enabled = bool(account.get('charges_enabled'))
        payouts_enabled = bool(account.get('payouts_enabled'))
        onboarding_completed = details_submitted and charges_enabled and payouts_enabled

        food_truck.stripe_details_submitted = details_submitted
        food_truck.stripe_charges_enabled = charges_enabled
        food_truck.stripe_payouts_enabled = payouts_enabled
        food_truck.stripe_onboarding_completed = onboarding_completed
        food_truck.save(
            update_fields=[
                'stripe_details_submitted',
                'stripe_charges_enabled',
                'stripe_payouts_enabled',
                'stripe_onboarding_completed',
            ]
        )
        return food_truck

    @classmethod
    def handle_account_updated(cls, event):
        account = (event.get('data') or {}).get('object') or {}
        account_id = account.get('id')
        metadata = account.get('metadata') or {}
        food_truck_id = metadata.get('food_truck_id')

        if food_truck_id:
            food_truck = FoodTruck.objects.filter(pk=food_truck_id).first()
        else:
            food_truck = FoodTruck.objects.filter(stripe_connect_account_id=account_id).first()

        if not food_truck:
            raise ValidationError('Food truck not found for Stripe Connect account.')

        if account_id and food_truck.stripe_connect_account_id != account_id:
            food_truck.stripe_connect_account_id = account_id
            food_truck.save(update_fields=['stripe_connect_account_id'])

        cls.sync_account_state(food_truck, account)
        return food_truck