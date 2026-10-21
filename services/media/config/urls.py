from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

urlpatterns = [
    path("api/media/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/media/docs/", SpectacularSwaggerView.as_view(url_name="schema")),
    path("", include("files.urls")),
]
