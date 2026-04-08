from django.urls import path
from .views import history, manage_pickup_slots

app_name = 'orders'

urlpatterns = [
    path('history/', history, name='history'),
    path('foodtruck/<slug:slug>/slots/', manage_pickup_slots, name='manage-pickup-slots'),
]
