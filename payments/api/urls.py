from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import (
    AccountingExportAPIView,
    PaymentViewSet,
    PaymentCreateAPIView,
    PaymentAuthorizeAPIView,
    PaymentCaptureAPIView,
    StripeConnectOnboardingAPIView,
    StripeConnectStatusAPIView,
    StripeWebhookAPIView,
)

router = DefaultRouter()
router.register(r'payments', PaymentViewSet)

urlpatterns = [
    path('payments/create/', PaymentCreateAPIView.as_view(), name='payment-create'),
    path('payments/authorize/', PaymentAuthorizeAPIView.as_view(), name='payment-authorize'),
    path('payments/capture/', PaymentCaptureAPIView.as_view(), name='payment-capture'),
    path('payments/accounting-export/', AccountingExportAPIView.as_view(), name='payment-accounting-export'),
    path('payments/connect/<slug:slug>/onboarding/', StripeConnectOnboardingAPIView.as_view(), name='payment-connect-onboarding'),
    path('payments/connect/<slug:slug>/status/', StripeConnectStatusAPIView.as_view(), name='payment-connect-status'),
    path('payments/webhook/', StripeWebhookAPIView.as_view(), name='payment-webhook'),
] + router.urls
