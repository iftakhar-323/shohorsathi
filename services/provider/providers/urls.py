from django.urls import path
from rest_framework.routers import SimpleRouter

from shohor_common.privacy import export_view

from . import privacy, views

router = SimpleRouter()
router.register("api/providers/jobs", views.JobViewSet, basename="job")
router.register("api/providers/payouts", views.PayoutViewSet, basename="payout")
router.register("api/admin/providers", views.AdminProviderViewSet, basename="admin-provider")
router.register("api/admin/jobs", views.AdminJobViewSet, basename="admin-job")
router.register("api/admin/payouts", views.AdminPayoutViewSet, basename="admin-payout")
router.register("api/admin/safety", views.AdminSafetyViewSet, basename="admin-safety")
router.register("api/admin/review-disputes", views.AdminDisputeViewSet, basename="admin-dispute")
router.register("api/admin/insurance-plans", views.AdminInsurancePlanViewSet, basename="admin-insurance-plan")
router.register("api/admin/insurance-claims", views.AdminClaimViewSet, basename="admin-insurance-claim")
router.register("api/admin/training-modules", views.AdminTrainingViewSet, basename="admin-training")

urlpatterns = [
    path("api/internal/export/<int:user_id>/", export_view(privacy.collect)),
    path("api/providers/register/", views.RegisterView.as_view()),
    path("api/providers/me/", views.MeView.as_view()),
    path("api/providers/me/location/", views.LocationView.as_view()),
    path("api/providers/earnings/", views.EarningsView.as_view()),
    path("api/providers/public/<int:pk>/", views.PublicProviderView.as_view()),
    path("api/providers/public/<int:pk>/reviews/", views.PublicReviewsView.as_view()),
    path("api/providers/reviews/", views.ReviewView.as_view()),
    path("api/providers/reviews/<int:pk>/dispute/", views.DisputeView.as_view()),
    path("api/providers/safety/sos/", views.SosView.as_view()),
    path("api/providers/share/", views.ShareView.as_view()),
    path("api/providers/share/<str:token>/", views.SharedJobView.as_view()),
    path("api/providers/insurance/", views.InsuranceView.as_view()),
    path("api/providers/insurance/claims/", views.ClaimView.as_view()),
    path("api/providers/training/", views.TrainingView.as_view()),
    path("api/providers/training/<slug:slug>/submit/", views.QuizView.as_view()),
    path("api/providers/certificates/<str:code>/", views.CertificateView.as_view()),
    path("api/internal/jobs/by-source/<str:source>/<int:source_id>/", views.InternalJobBySourceView.as_view()),
    path("api/providers/tracking/<str:source>/<int:source_id>/", views.JobLocationView.as_view()),
    path("api/admin/provider-stats/", views.AdminStatsView.as_view()),
    path("api/internal/providers/by-user/<int:user_id>/", views.InternalProviderView.as_view()),
] + router.urls
