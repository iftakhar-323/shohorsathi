from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView
from shohor_common.health import health_urls

urlpatterns = health_urls("custom_request") + [
    path("api/custom_request/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/custom_request/docs/", SpectacularSwaggerView.as_view(url_name="schema")),
    path("", include("custom_requests.urls")),
]
