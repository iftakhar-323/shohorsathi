from django.urls import path
from rest_framework.routers import SimpleRouter

from . import views

router = SimpleRouter()
router.register("api/payments/agreements", views.PaymentAgreementViewSet, basename="payment-agreement")
router.register("api/payments/mine", views.MyPaymentViewSet, basename="my-payment")
router.register("api/admin/payments", views.AdminPaymentViewSet, basename="admin-payment")
router.register("api/admin/refunds", views.AdminRefundViewSet, basename="admin-refund")

urlpatterns = [
    path("api/payments/initiate/", views.InitiateView.as_view()),
    path("api/payments/gateway/success/", views.GatewayReturnView.as_view(outcome="success")),
    path("api/payments/gateway/fail/", views.GatewayReturnView.as_view(outcome="fail")),
    path("api/payments/gateway/cancel/", views.GatewayReturnView.as_view(outcome="cancel")),
    path("api/payments/gateway/ipn/", views.IpnView.as_view()),
    path("api/payments/mock/<str:tran_id>/", views.MockGatewayPage.as_view()),
    path("api/payments/bkash/mock/<str:tran_id>/", views.MockBkashPage.as_view()),
    path("api/payments/nagad/mock/<str:tran_id>/", views.MockNagadPage.as_view()),
    path("api/payments/bkash/agreement/mock/", views.MockAgreementPage.as_view()),
    path("api/internal/charge-agreement/", views.InternalChargeAgreementView.as_view()),
] + router.urls
