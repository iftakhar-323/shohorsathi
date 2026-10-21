from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

urlpatterns = [
    path("api/loyalty/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/loyalty/docs/", SpectacularSwaggerView.as_view(url_name="schema")),
    path("", include("loyalty.urls")),
]
