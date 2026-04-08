from django.urls import path
from rest_framework.routers import DefaultRouter
from .views import (
    OrderViewSet,
    CartView,
    CartAddView,
    CartRemoveView,
    CartCheckoutView,
    PickupSlotListView,
    SetOrderPickupSlotView,
    SubmitOrderView,
    PickupSlotViewSet,
)

router = DefaultRouter()
router.register(r'orders', OrderViewSet)
router.register(r'pickup-slots', PickupSlotViewSet, basename='pickup-slot')

urlpatterns = [
    path('cart/', CartView.as_view(), name='cart-detail'),
    path('cart/add/', CartAddView.as_view(), name='cart-add'),
    path('cart/remove/', CartRemoveView.as_view(), name='cart-remove'),
    path('cart/checkout/', CartCheckoutView.as_view(), name='cart-checkout'),
    path('orders/set-slot/', SetOrderPickupSlotView.as_view(), name='order-set-slot'),
    path('orders/submit/', SubmitOrderView.as_view(), name='order-finalize'),
    path('foodtrucks/<slug:slug>/pickup-slots/', PickupSlotListView.as_view(), name='foodtruck-pickup-slots'),
]

urlpatterns += router.urls
