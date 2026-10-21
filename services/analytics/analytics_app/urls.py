from django.urls import path

from . import views

urlpatterns = [
    path("api/admin/analytics/summary/", views.SummaryView.as_view()),
    path("api/admin/analytics/heatmap/", views.HeatmapView.as_view()),
]
