from rest_framework.routers import SimpleRouter

from . import views

router = SimpleRouter()
router.register("api/categories", views.CategoryViewSet, basename="category")
router.register("api/products", views.ProductViewSet, basename="product")
router.register("api/services", views.ServiceViewSet, basename="service")

urlpatterns = router.urls
