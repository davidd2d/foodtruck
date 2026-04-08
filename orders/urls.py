from django.urls import path
from .views import history

app_name = 'orders'

urlpatterns = [
    path('history/', history, name='history'),
]
