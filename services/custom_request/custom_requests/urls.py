from django.urls import path
from rest_framework.routers import SimpleRouter

from . import views

router = SimpleRouter()
router.register("api/custom-requests", views.CustomRequestViewSet, basename="custom-request")
router.register("api/admin/custom-requests", views.AdminCustomRequestViewSet, basename="admin-custom-request")

urlpatterns = [
    path("api/internal/custom-requests/<int:pk>/payable/", views.AdvancePayableView.as_view()),
] + router.urls
