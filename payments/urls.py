from django.urls import path

from .views import PaymentPageView, PaymentSuccessView

app_name = 'payments'

urlpatterns = [
    path('checkout/<int:order_id>/', PaymentPageView.as_view(), name='checkout'),
    path('success/', PaymentSuccessView.as_view(), name='success'),
]
