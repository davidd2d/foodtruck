from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.utils.dateparse import parse_date
from django.core.exceptions import ValidationError
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from rest_framework import viewsets, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from stripe.error import SignatureVerificationError

from foodtrucks.models import FoodTruck
from orders.models import Order
from payments.models import Payment
from payments.services.accounting_export_service import AccountingExportService
from payments.services.payment_service import PaymentService
from payments.services.stripe_connect_service import StripeConnectService
from payments.services.stripe_webhook_service import StripeWebhookService
from .serializers import PaymentSerializer


class PaymentViewSet(viewsets.ReadOnlyModelViewSet):
    """Read-only access to payments owned by the current user."""
    queryset = Payment.objects.all()
    serializer_class = PaymentSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Payment.objects.filter(
            order__user=self.request.user
        ).select_related('order')


class PaymentCreateAPIView(APIView):
    """Create a simulated payment in the pending state."""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        order_id = request.data.get('order_id')

        if not order_id:
            return Response({'detail': 'order_id is required'}, status=status.HTTP_400_BAD_REQUEST)

        order = Order.objects.filter(
            id=order_id,
            user=request.user
        ).select_related('payment').first()

        if not order:
            return Response({'detail': 'Order not found'}, status=status.HTTP_404_NOT_FOUND)

        try:
            payment = PaymentService.create_payment(order)
        except ValidationError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        serializer = PaymentSerializer(payment)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class PaymentAuthorizeAPIView(APIView):
    """Transition a pending payment to authorized."""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        payment_id = request.data.get('payment_id')

        if not payment_id:
            return Response({'detail': 'payment_id is required'}, status=status.HTTP_400_BAD_REQUEST)

        payment = Payment.objects.filter(
            pk=payment_id,
            order__user=request.user
        ).select_related('order').first()

        if not payment:
            return Response({'detail': 'Payment not found'}, status=status.HTTP_404_NOT_FOUND)

        try:
            payment = PaymentService.authorize_payment(payment)
        except ValidationError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        serializer = PaymentSerializer(payment)
        return Response(serializer.data, status=status.HTTP_200_OK)


class PaymentCaptureAPIView(APIView):
    """Capture funds and mark the order as paid."""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        payment_id = request.data.get('payment_id')

        if not payment_id:
            return Response({'detail': 'payment_id is required'}, status=status.HTTP_400_BAD_REQUEST)

        payment = Payment.objects.filter(
            pk=payment_id,
            order__user=request.user
        ).select_related('order').first()

        if not payment:
            return Response({'detail': 'Payment not found'}, status=status.HTTP_404_NOT_FOUND)

        try:
            payment = PaymentService.capture_payment(payment)
        except ValidationError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        serializer = PaymentSerializer(payment)
        return Response(serializer.data, status=status.HTTP_200_OK)


class AccountingExportAPIView(APIView):
    """Download paid-order accounting exports scoped to the authenticated operator."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        start_date = parse_date(request.query_params.get('start_date', ''))
        end_date = parse_date(request.query_params.get('end_date', ''))
        slug = request.query_params.get('foodtruck')

        if not start_date or not end_date:
            return Response({'detail': 'start_date and end_date are required (YYYY-MM-DD).'}, status=status.HTTP_400_BAD_REQUEST)
        if end_date < start_date:
            return Response({'detail': 'end_date must be greater than or equal to start_date.'}, status=status.HTTP_400_BAD_REQUEST)

        food_truck = None
        if slug:
            food_truck = get_object_or_404(FoodTruck, slug=slug)
            if not (request.user.is_superuser or request.user.can_manage_foodtruck(food_truck)):
                return Response({'detail': 'You do not have access to this food truck.'}, status=status.HTTP_403_FORBIDDEN)

        if request.user.is_superuser:
            owner = None
        else:
            owner = request.user

        csv_content = AccountingExportService.export_orders_csv(
            start_date,
            end_date,
            user=request.user,
            owner=owner,
            food_truck=food_truck,
        )

        filename_parts = ['accounting-export', str(start_date), str(end_date)]
        if food_truck is not None:
            filename_parts.append(food_truck.slug)
        response = HttpResponse(csv_content, content_type='text/csv; charset=utf-8')
        response['Content-Disposition'] = f'attachment; filename="{"-".join(filename_parts)}.csv"'
        return response


class StripeConnectOnboardingAPIView(APIView):
    """Create or refresh a Stripe Connect onboarding link for the owned food truck."""

    permission_classes = [IsAuthenticated]

    def post(self, request, slug):
        food_truck = get_object_or_404(FoodTruck, slug=slug, is_active=True)
        if not (request.user.is_superuser or request.user.can_manage_foodtruck(food_truck)):
            return Response({'detail': 'You do not have access to this food truck.'}, status=status.HTTP_403_FORBIDDEN)

        refresh_url = request.build_absolute_uri(request.path)
        return_url = request.build_absolute_uri(f'/foodtrucks/{food_truck.slug}/')

        try:
            onboarding_url = StripeConnectService.create_onboarding_link(
                food_truck,
                refresh_url=refresh_url,
                return_url=return_url,
            )
        except ValidationError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        food_truck.refresh_from_db()
        return Response({
            'onboarding_url': onboarding_url,
            'stripe_connect_account_id': food_truck.stripe_connect_account_id,
            'onboarding_completed': food_truck.stripe_onboarding_completed,
        }, status=status.HTTP_200_OK)


class StripeConnectStatusAPIView(APIView):
    """Expose the current Stripe Connect state for the owned food truck."""

    permission_classes = [IsAuthenticated]

    def get(self, request, slug):
        food_truck = get_object_or_404(FoodTruck, slug=slug, is_active=True)
        if not (request.user.is_superuser or request.user.can_manage_foodtruck(food_truck)):
            return Response({'detail': 'You do not have access to this food truck.'}, status=status.HTTP_403_FORBIDDEN)

        return Response({
            'stripe_connect_account_id': food_truck.stripe_connect_account_id,
            'details_submitted': food_truck.stripe_details_submitted,
            'charges_enabled': food_truck.stripe_charges_enabled,
            'payouts_enabled': food_truck.stripe_payouts_enabled,
            'onboarding_completed': food_truck.stripe_onboarding_completed,
        }, status=status.HTTP_200_OK)


@method_decorator(csrf_exempt, name='dispatch')
class StripeWebhookAPIView(APIView):
    """Stripe webhook endpoint. Signature check and processing are service-driven."""

    permission_classes = []
    authentication_classes = []

    def post(self, request):
        payload = request.body
        sig_header = request.META.get('HTTP_STRIPE_SIGNATURE')

        if not sig_header:
            return Response({'detail': 'Missing Stripe signature header.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            event = StripeWebhookService.construct_event(payload, sig_header)
            StripeWebhookService.handle_event(event)
        except (ValueError, SignatureVerificationError, ValidationError):
            return Response({'detail': 'Invalid webhook payload.'}, status=status.HTTP_400_BAD_REQUEST)

        return Response({'status': 'ok'}, status=status.HTTP_200_OK)
