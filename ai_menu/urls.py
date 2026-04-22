from django.urls import path

from ai_menu import views

app_name = 'ai_menu'

urlpatterns = [
    path('dashboard/foodtruck/<slug:slug>/menu-ai/', views.dashboard, name='dashboard'),
    path('dashboard/foodtruck/<slug:slug>/combos/', views.combo_list, name='combo-list'),
    path('dashboard/foodtruck/<slug:slug>/combos/create/', views.combo_create, name='combo-create'),
    path('dashboard/foodtruck/<slug:slug>/combos/<int:combo_id>/edit/', views.combo_edit, name='combo-edit'),
    path('dashboard/menu/items/<int:item_id>/analyze-ai/', views.analyze_item, name='analyze-item'),
    path('dashboard/ai-recommendations/<int:recommendation_id>/decision/', views.recommendation_decision, name='recommendation-decision'),
]