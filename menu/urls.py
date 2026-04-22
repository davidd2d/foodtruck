from django.urls import path

from menu import views

app_name = 'menu'

urlpatterns = [
    path('dashboard/foodtruck/<slug:slug>/menu/', views.owner_menu_dashboard, name='dashboard'),
    path('dashboard/foodtruck/<slug:slug>/menu/import/', views.owner_menu_import, name='import'),
    path('dashboard/foodtruck/<slug:slug>/menu/catalog/', views.owner_menu_catalog, name='catalog'),
    path('dashboard/foodtruck/<slug:slug>/menu/items/<int:item_id>/update/', views.owner_item_update, name='update-item'),
    path('dashboard/foodtruck/<slug:slug>/menu/combos/<int:combo_id>/update/', views.owner_combo_update, name='update-combo'),
    path('dashboard/foodtruck/<slug:slug>/menu/options/<int:option_id>/update/', views.owner_option_update, name='update-option'),
]