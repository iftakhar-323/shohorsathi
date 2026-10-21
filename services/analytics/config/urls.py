from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

urlpatterns = [
    path("api/analytics/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/analytics/docs/", SpectacularSwaggerView.as_view(url_name="schema")),
    path("", include("analytics_app.urls")),
]
