from django.urls import path

from .views import PaymentPageView, PaymentSuccessView

app_name = 'payments'

urlpatterns = [
    path('foodtruck/<slug:slug>/checkout/<int:order_id>/', PaymentPageView.as_view(), name='checkout'),
    path('foodtruck/<slug:slug>/success/<int:order_id>/', PaymentSuccessView.as_view(), name='success'),
]
