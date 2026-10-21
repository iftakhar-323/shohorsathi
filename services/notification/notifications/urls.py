from django.urls import path
from rest_framework.routers import SimpleRouter

from . import views

router = SimpleRouter()
router.register("api/notifications", views.NotificationViewSet, basename="notification")

urlpatterns = [
    path("api/admin/notifications/broadcast/", views.BroadcastView.as_view()),
    path("api/admin/notifications/sms-log/", views.SmsLogView.as_view()),
] + router.urls
