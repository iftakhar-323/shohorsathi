from rest_framework.routers import SimpleRouter

from . import views

router = SimpleRouter()
router.register("api/custom-requests", views.CustomRequestViewSet, basename="custom-request")
router.register("api/admin/custom-requests", views.AdminCustomRequestViewSet, basename="admin-custom-request")

urlpatterns = router.urls
