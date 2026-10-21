from django.urls import path
from rest_framework.routers import SimpleRouter

from shohor_common.privacy import export_view

from . import privacy, views

router = SimpleRouter()
router.register("api/custom-requests", views.CustomRequestViewSet, basename="custom-request")
router.register("api/admin/custom-requests", views.AdminCustomRequestViewSet, basename="admin-custom-request")

urlpatterns = [
    path("api/internal/export/<int:user_id>/", export_view(privacy.collect)),
    path("api/internal/custom-requests/<int:pk>/payable/", views.AdvancePayableView.as_view()),
] + router.urls
