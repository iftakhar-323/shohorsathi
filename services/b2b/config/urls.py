from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView
from shohor_common.health import health_urls

urlpatterns = health_urls("b2b") + [
    path("api/b2b/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/b2b/docs/", SpectacularSwaggerView.as_view(url_name="schema")),
    path("", include("b2b_app.urls")),
]
