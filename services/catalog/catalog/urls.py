from django.urls import path
from rest_framework.routers import SimpleRouter

from . import views

router = SimpleRouter()
router.register("api/categories", views.CategoryViewSet, basename="category")
router.register("api/products", views.ProductViewSet, basename="product")
router.register("api/services", views.ServiceViewSet, basename="service")
router.register("api/group-deals", views.GroupDealViewSet, basename="group-deal")
router.register("api/seasonal-packages", views.SeasonalPackageViewSet, basename="seasonal-package")

urlpatterns = [
    path("api/internal/group-deals/discount/", views.GroupDealDiscountView.as_view()),
    path("api/catalog/sponsored/", views.SponsoredPlacementListView.as_view()),
] + router.urls
