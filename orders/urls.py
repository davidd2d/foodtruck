from django.urls import path

from .views import (
    history,
    manage_pickup_slots,
    working_hours,
    LocationListView,
    LocationCreateView,
    LocationUpdateView,
    LocationDeleteView,
)

app_name = 'orders'

urlpatterns = [
    path('history/', history, name='history'),
    path('foodtruck/<slug:slug>/slots/', manage_pickup_slots, name='manage-pickup-slots'),
    path('foodtruck/<slug:slug>/locations/', LocationListView.as_view(), name='location-list'),
    path('foodtruck/<slug:slug>/locations/create/', LocationCreateView.as_view(), name='location-create'),
    path('foodtruck/<slug:slug>/locations/<int:pk>/edit/', LocationUpdateView.as_view(), name='location-edit'),
    path('foodtruck/<slug:slug>/locations/<int:pk>/delete/', LocationDeleteView.as_view(), name='location-delete'),
    path('foodtruck/<slug:slug>/schedules/', working_hours, name='working-hours'),
]
