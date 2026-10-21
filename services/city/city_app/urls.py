from django.urls import path
from rest_framework.routers import SimpleRouter

from shohor_common.privacy import export_view

from . import privacy, views

router = SimpleRouter()
router.register("api/issues", views.IssueViewSet, basename="issue")
router.register("api/community/posts", views.PostViewSet, basename="post")
router.register("api/admin/issues", views.AdminIssueViewSet, basename="admin-issue")
router.register("api/admin/authorities", views.AuthorityViewSet, basename="admin-authority")

urlpatterns = [
    path("api/internal/export/<int:user_id>/", export_view(privacy.collect)),
    path("api/admin/community/posts/<int:pk>/hide/", views.AdminHidePostView.as_view()),
] + router.urls
