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
    path('<slug:slug>/', views.foodtruck_detail, name='foodtruck-detail'),
]