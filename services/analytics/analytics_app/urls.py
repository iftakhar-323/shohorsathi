from django.urls import path

from . import views

urlpatterns = [
    path("api/admin/analytics/summary/", views.SummaryView.as_view()),
    path("api/admin/analytics/heatmap/", views.HeatmapView.as_view()),
    path("api/admin/analytics/forecast/", views.ForecastView.as_view()),
    path("api/admin/analytics/churn/", views.ChurnView.as_view()),
    path("api/admin/analytics/churn/winback/", views.WinbackView.as_view()),
    path("api/admin/analytics/fraud/", views.FraudView.as_view()),
    path("api/admin/analytics/revenue/", views.RevenueView.as_view()),
]
