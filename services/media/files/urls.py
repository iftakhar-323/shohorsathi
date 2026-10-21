from django.urls import path

from . import views

urlpatterns = [
    path("api/media/", views.UploadView.as_view()),
    path("api/media/<int:pk>/download/", views.DownloadView.as_view()),
    path("api/internal/media/delete/", views.InternalDeleteView.as_view()),
    path("api/admin/media/<int:pk>/access-log/", views.AccessLogView.as_view()),
]
