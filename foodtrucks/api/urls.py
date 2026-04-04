from rest_framework.routers import DefaultRouter
from .views import FoodTruckViewSet

router = DefaultRouter()
router.register(r'foodtrucks', FoodTruckViewSet)

urlpatterns = router.urls