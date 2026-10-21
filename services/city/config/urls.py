from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

urlpatterns = [
    path("api/city/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/city/docs/", SpectacularSwaggerView.as_view(url_name="schema")),
    path("", include("city_app.urls")),
]
