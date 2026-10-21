from django.urls import path
from rest_framework.routers import SimpleRouter

from shohor_common.privacy import export_view

from . import privacy, views

router = SimpleRouter()
router.register("api/cart/items", views.CartItemViewSet, basename="cart-item")
router.register("api/orders", views.OrderViewSet, basename="order")
router.register("api/bookings", views.BookingViewSet, basename="booking")
router.register("api/admin/orders", views.AdminOrderViewSet, basename="admin-order")
router.register("api/admin/bookings", views.AdminBookingViewSet, basename="admin-booking")
router.register("api/admin/warranty-claims", views.AdminWarrantyViewSet, basename="admin-warranty")

urlpatterns = [
    path("api/internal/export/<int:user_id>/", export_view(privacy.collect)),
    path("api/cart/", views.CartView.as_view()),
    path("api/admin/order-stats/", views.AdminStatsView.as_view()),
    path("api/internal/bookings/<int:pk>/verify-arrival/", views.VerifyArrivalView.as_view()),
    path("api/internal/orders/<int:pk>/payable/", views.OrderPayableView.as_view()),
    path("api/internal/orders/", views.InternalOrganizationOrdersView.as_view()),
] + router.urls
