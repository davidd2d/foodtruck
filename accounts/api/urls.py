from django.urls import path

from .views import LoginAPIView, RefreshAPIView, LogoutAPIView

app_name = 'accounts_api'

urlpatterns = [
    path('login/', LoginAPIView.as_view(), name='login'),
    path('refresh/', RefreshAPIView.as_view(), name='refresh'),
    path('logout/', LogoutAPIView.as_view(), name='logout'),
]
