from django.urls import path

from . import views

urlpatterns = [
    path("api/loyalty/me/", views.MeView.as_view()),
    path("api/loyalty/referral/", views.ReferralView.as_view()),
    path("api/loyalty/topups/", views.TopUpView.as_view()),
    path("api/internal/loyalty/redeem-points/", views.InternalRedeemPoints.as_view()),
    path("api/internal/loyalty/wallet-pay/", views.InternalWalletPay.as_view()),
    path("api/internal/loyalty/reverse/", views.InternalReverse.as_view()),
    path("api/internal/loyalty/topups/<int:pk>/payable/", views.InternalTopUpPayable.as_view()),
    path("api/admin/loyalty/accounts/", views.AdminAccountsView.as_view()),
    path("api/admin/loyalty/accounts/<int:user_id>/adjust/", views.AdminAdjustView.as_view()),
]
