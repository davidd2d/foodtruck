from django.urls import path
from . import views

app_name = 'foodtrucks'

urlpatterns = [
    path('', views.foodtruck_list, name='list'),
]