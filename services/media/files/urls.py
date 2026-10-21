from django.urls import path

from . import views

urlpatterns = [
    path("api/media/", views.UploadView.as_view()),
    path("api/media/<int:pk>/download/", views.DownloadView.as_view()),
]
