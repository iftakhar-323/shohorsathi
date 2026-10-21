from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

urlpatterns = [
    path("api/payment/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/payment/docs/", SpectacularSwaggerView.as_view(url_name="schema")),
    path("", include("payments.urls")),
]
