from django.urls import path

from shohor_common.privacy import export_view

from . import privacy, views

urlpatterns = [
    path("api/internal/export/<int:user_id>/", export_view(privacy.collect)),
    path("api/loyalty/me/", views.MeView.as_view()),
    path("api/loyalty/referral/", views.ReferralView.as_view()),
    path("api/internal/loyalty/redeem-points/", views.InternalRedeemPoints.as_view()),
    path("api/internal/loyalty/wallet-pay/", views.InternalWalletPay.as_view()),
    path("api/internal/loyalty/reverse/", views.InternalReverse.as_view()),
    path("api/admin/loyalty/accounts/", views.AdminAccountsView.as_view()),
    path("api/admin/loyalty/accounts/<int:user_id>/adjust/", views.AdminAdjustView.as_view()),
]
