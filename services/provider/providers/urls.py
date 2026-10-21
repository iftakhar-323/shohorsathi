from django.urls import path
from rest_framework.routers import SimpleRouter

from . import views

router = SimpleRouter()
router.register("api/providers/jobs", views.JobViewSet, basename="job")
router.register("api/providers/payouts", views.PayoutViewSet, basename="payout")
router.register("api/admin/providers", views.AdminProviderViewSet, basename="admin-provider")
router.register("api/admin/jobs", views.AdminJobViewSet, basename="admin-job")
router.register("api/admin/payouts", views.AdminPayoutViewSet, basename="admin-payout")

urlpatterns = [
    path("api/providers/register/", views.RegisterView.as_view()),
    path("api/providers/me/", views.MeView.as_view()),
    path("api/providers/me/location/", views.LocationView.as_view()),
    path("api/providers/earnings/", views.EarningsView.as_view()),
    path("api/providers/public/<int:pk>/", views.PublicProviderView.as_view()),
    path("api/providers/tracking/<str:source>/<int:source_id>/", views.JobLocationView.as_view()),
    path("api/admin/provider-stats/", views.AdminStatsView.as_view()),
    path("api/internal/providers/by-user/<int:user_id>/", views.InternalProviderView.as_view()),
] + router.urls
