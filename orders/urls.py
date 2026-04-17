from django.urls import path
from orders.api.views import OrderDashboardAPIView, OrderStatusUpdateAPIView

from .views import (
    history,
    manage_pickup_slots,
    working_hours,
    OrderDashboardView,
    LocationListView,
    LocationCreateView,
    LocationUpdateView,
    LocationDeleteView,
    TicketListView,
    TicketDetailView,
    OwnerTicketListView,
)

app_name = 'orders'

urlpatterns = [
    path('history/', history, name='history'),
    path('foodtruck/<slug:slug>/users/<int:user_id>/tickets/', TicketListView.as_view(), name='ticket-list-page'),
    path('foodtruck/<slug:slug>/users/<int:user_id>/tickets/<int:ticket_id>/', TicketDetailView.as_view(), name='ticket-detail-page'),
    path('foodtruck/<slug:slug>/owner/tickets/', OwnerTicketListView.as_view(), name='owner-ticket-list'),
    path('foodtruck/<slug:slug>/dashboard/', OrderDashboardView.as_view(), name='dashboard'),
    path('foodtruck/<slug:slug>/slots/', manage_pickup_slots, name='manage-pickup-slots'),
    path('foodtruck/<slug:slug>/locations/', LocationListView.as_view(), name='location-list'),
    path('foodtruck/<slug:slug>/locations/create/', LocationCreateView.as_view(), name='location-create'),
    path('foodtruck/<slug:slug>/locations/<int:pk>/edit/', LocationUpdateView.as_view(), name='location-edit'),
    path('foodtruck/<slug:slug>/locations/<int:pk>/delete/', LocationDeleteView.as_view(), name='location-delete'),
    path('foodtruck/<slug:slug>/schedules/', working_hours, name='working-hours'),
    path('api/dashboard/', OrderDashboardAPIView.as_view(), name='dashboard-api'),
    path('api/<int:order_id>/status/', OrderStatusUpdateAPIView.as_view(), name='dashboard-status-api'),
]
