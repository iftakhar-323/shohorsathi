from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView
from shohor_common.health import health_urls

urlpatterns = health_urls("provider") + [
    path("api/provider/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/provider/docs/", SpectacularSwaggerView.as_view(url_name="schema")),
    path("", include("providers.urls")),
]
