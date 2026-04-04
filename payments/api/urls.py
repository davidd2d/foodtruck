from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import (
    PaymentViewSet,
    PaymentCreateAPIView,
    PaymentAuthorizeAPIView,
    PaymentCaptureAPIView,
)

router = DefaultRouter()
router.register(r'payments', PaymentViewSet)

urlpatterns = [
    path('payments/create/', PaymentCreateAPIView.as_view(), name='payment-create'),
    path('payments/authorize/', PaymentAuthorizeAPIView.as_view(), name='payment-authorize'),
    path('payments/capture/', PaymentCaptureAPIView.as_view(), name='payment-capture'),
] + router.urls
