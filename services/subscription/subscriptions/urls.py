from django.urls import path
from rest_framework.routers import SimpleRouter

from shohor_common.privacy import export_view

from . import privacy, views

router = SimpleRouter()
router.register("api/subscription-plans", views.PlanViewSet, basename="plan")
router.register("api/subscription-addons", views.AddonViewSet, basename="addon")
router.register("api/subscriptions/visits", views.VisitViewSet, basename="visit")
router.register("api/subscriptions", views.SubscriptionViewSet, basename="subscription")
router.register("api/meal-menu", views.MenuViewSet, basename="menu")
router.register("api/admin/subscriptions", views.AdminSubscriptionViewSet, basename="admin-subscription")
router.register("api/admin/plan-prices", views.PlanPriceViewSet, basename="admin-plan-price")
router.register("api/admin/student-verifications", views.AdminStudentViewSet, basename="admin-student")

urlpatterns = [
    path("api/internal/export/<int:user_id>/", export_view(privacy.collect)),
    path("api/subscriptions/quote/", views.QuoteView.as_view()),
    path("api/subscriptions/student-verification/", views.StudentVerificationView.as_view()),
    path("api/admin/subscription-stats/", views.AdminStatsView.as_view()),
    path("api/internal/subscriptions/<int:pk>/payable/", views.InternalPayableView.as_view()),
] + router.urls
