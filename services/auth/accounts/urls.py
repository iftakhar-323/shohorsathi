from django.urls import path
from rest_framework.routers import SimpleRouter
from rest_framework_simplejwt.views import TokenRefreshView

from . import views

router = SimpleRouter()
router.register("api/me/addresses", views.AddressViewSet, basename="address")

urlpatterns = [
    path("api/auth/otp/request/", views.OtpRequestView.as_view()),
    path("api/auth/register/", views.RegisterView.as_view()),
    path("api/auth/login/", views.LoginView.as_view()),
    path("api/auth/token/refresh/", TokenRefreshView.as_view()),
    path("api/auth/password/reset/", views.PasswordResetView.as_view()),
    path("api/me/", views.MeView.as_view()),
    path("api/areas/", views.AreaListView.as_view()),
] + router.urls
