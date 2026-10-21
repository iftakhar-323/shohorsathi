from django.urls import path

from . import views

urlpatterns = [
    path("api/b2b/orgs/", views.OrgsView.as_view()),
    path("api/b2b/orgs/<int:pk>/", views.OrgDetailView.as_view()),
    path("api/b2b/orgs/<int:pk>/members/", views.MembersView.as_view()),
    path("api/b2b/orgs/<int:pk>/invoices/", views.InvoicesView.as_view()),
    path("api/b2b/invoices/<int:pk>/print/", views.InvoicePrintView.as_view()),
    path("api/internal/b2b/membership/", views.InternalMembershipView.as_view()),
    path("api/admin/b2b/orgs/", views.AdminOrgsView.as_view()),
    path("api/admin/b2b/orgs/<int:pk>/<str:action>/", views.AdminOrgActionView.as_view()),
    path("api/admin/b2b/invoices/", views.AdminInvoicesView.as_view()),
    path("api/admin/b2b/invoices/<int:pk>/mark-paid/", views.AdminInvoicePaidView.as_view()),
]
