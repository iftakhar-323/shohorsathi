from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

urlpatterns = [
    path("api/chat/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/chat/docs/", SpectacularSwaggerView.as_view(url_name="schema")),
    path("", include("chat_app.urls")),
]
