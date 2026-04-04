from django.urls import path
from rest_framework.routers import DefaultRouter
from .views import MenuViewSet, FoodTruckMenuView

router = DefaultRouter()
router.register(r'menu', MenuViewSet)

urlpatterns = [
    path('foodtrucks/<slug:slug>/menu/', FoodTruckMenuView.as_view(), name='foodtruck-menu'),
]

urlpatterns += router.urls