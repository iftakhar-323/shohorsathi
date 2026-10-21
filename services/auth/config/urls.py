from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

urlpatterns = [
    path("api/auth/admin/", admin.site.urls),
    path("api/auth/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/auth/docs/", SpectacularSwaggerView.as_view(url_name="schema")),
    path("", include("accounts.urls")),
]
