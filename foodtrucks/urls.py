from django.urls import path
from . import views
from .diagnostic_view import diagnostic_view
from .menu_test_view import test_menu_api
from .list_trucks_view import list_foodtrucks_view
from .menu_test_page import menu_test_page

app_name = 'foodtrucks'

urlpatterns = [
    path('', views.foodtruck_list, name='foodtruck-list'),
    path('diagnostic/', diagnostic_view, name='diagnostic'),
    path('test-menu-api/', test_menu_api, name='test-menu-api'),
    path('test-menu-page/', menu_test_page, name='test-menu-page'),
    path('list-api/', list_foodtrucks_view, name='list-foodtrucks-api'),
    path('<slug:slug>/dashboard/', views.FoodTruckDashboardView.as_view(), name='foodtruck-dashboard'),
    path('<slug:slug>/dashboard/kpis/', views.DashboardKpiAPIView.as_view(), name='foodtruck-dashboard-kpis'),
    path('<slug:slug>/dashboard/revenue/', views.DashboardRevenueAPIView.as_view(), name='foodtruck-dashboard-revenue'),
    path('<slug:slug>/dashboard/orders/', views.DashboardOrdersAPIView.as_view(), name='foodtruck-dashboard-orders'),
    path('<slug:slug>/dashboard/menu-performance/', views.DashboardMenuPerformanceAPIView.as_view(), name='foodtruck-dashboard-menu-performance'),
    path('<slug:slug>/dashboard/menu-categories/', views.DashboardMenuCategoryPerformanceAPIView.as_view(), name='foodtruck-dashboard-menu-categories'),
    path('<slug:slug>/dashboard/slots/', views.DashboardSlotPerformanceAPIView.as_view(), name='foodtruck-dashboard-slots'),
    path('<slug:slug>/dashboard/slots/utilization/', views.DashboardSlotUtilizationAPIView.as_view(), name='foodtruck-dashboard-slots-utilization'),
    path('<slug:slug>/dashboard/slots/revenue/', views.DashboardSlotRevenueAPIView.as_view(), name='foodtruck-dashboard-slots-revenue'),
    path('<slug:slug>/dashboard/slots/hourly/', views.DashboardSlotHourlyAPIView.as_view(), name='foodtruck-dashboard-slots-hourly'),
    path('<slug:slug>/dashboard/slots/heatmap/', views.DashboardSlotHeatmapAPIView.as_view(), name='foodtruck-dashboard-slots-heatmap'),
    path('<slug:slug>/dashboard/slots/insights/', views.DashboardSlotInsightsAPIView.as_view(), name='foodtruck-dashboard-slots-insights'),
    path('<slug:slug>/dashboard/slots/recommendations/', views.DashboardSlotRecommendationsAPIView.as_view(), name='foodtruck-dashboard-slots-recommendations'),
    path('<slug:slug>/dashboard/options/', views.DashboardOptionPerformanceAPIView.as_view(), name='foodtruck-dashboard-options'),
    path('<slug:slug>/', views.foodtruck_detail, name='foodtruck-detail'),
]