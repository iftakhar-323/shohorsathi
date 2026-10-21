from django.db.models import Count, Q, Sum
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import generics, mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView
from shohor_common.internal import IsInternal
from shohor_common.permissions import IsAdmin

from . import logic
from .models import Booking, Cart, CartItem, Order, WarrantyClaim
from .serializers import (
    AddToCartSerializer,
    AdminBookingSerializer,
    AdminOrderSerializer,
    BookingSerializer,
    CartItemSerializer,
    CartSerializer,
    CheckoutSerializer,
    OrderSerializer,
    RescheduleSerializer,
    TrackingEventSerializer,
    WarrantyClaimSerializer,
)


def uid(request):
    return int(request.user.id)


class CartView(APIView):
    def get(self, request):
        cart, _ = Cart.objects.get_or_create(user_id=uid(request))
        return Response(CartSerializer(cart).data)

    def delete(self, request):
        CartItem.objects.filter(cart__user_id=uid(request)).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class CartItemViewSet(mixins.CreateModelMixin, mixins.UpdateModelMixin, mixins.DestroyModelMixin, viewsets.GenericViewSet):
    serializer_class = CartItemSerializer

    def get_queryset(self):
        return CartItem.objects.filter(cart__user_id=uid(self.request))

    def create(self, request):
        data = AddToCartSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        item = logic.add_to_cart(uid(request), **data.validated_data)
        return Response(CartItemSerializer(item).data, status=status.HTTP_201_CREATED)

    def perform_update(self, serializer):
        if serializer.instance.item_type == "service":
            serializer.save(quantity=1)
        else:
            serializer.save()


class OrderViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, mixins.CreateModelMixin, viewsets.GenericViewSet):
    serializer_class = OrderSerializer

    def get_queryset(self):
        return Order.objects.filter(user_id=uid(self.request)).prefetch_related("items", "bookings")

    def create(self, request):
        data = CheckoutSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        order = logic.checkout(uid(request), data.validated_data)
        return Response(OrderSerializer(order).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        order = self.get_object()
        logic.cancel_order(order)
        return Response(OrderSerializer(order).data)

    @action(detail=True)
    def tracking(self, request, pk=None):
        order = self.get_object()
        return Response({"status": order.status, "events": TrackingEventSerializer(order.events.all(), many=True).data})


class BookingViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    serializer_class = BookingSerializer

    def get_queryset(self):
        qs = Booking.objects.filter(user_id=uid(self.request)).select_related("order")
        if s := self.request.query_params.get("status"):
            qs = qs.filter(status=s)
        return qs.order_by("-created_at")

    @action(detail=True, methods=["patch"])
    def reschedule(self, request, pk=None):
        booking = self.get_object()
        data = RescheduleSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        logic.reschedule(booking, **data.validated_data)
        return Response(BookingSerializer(booking).data)

    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        booking = self.get_object()
        logic.cancel_booking(booking)
        return Response(BookingSerializer(booking).data)

    @action(detail=True, methods=["post"])
    def warranty(self, request, pk=None):
        data = WarrantyClaimSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        claim = logic.open_warranty_claim(
            self.get_object(), data.validated_data["description"], data.validated_data.get("photo_urls", [])
        )
        return Response(WarrantyClaimSerializer(claim).data, status=status.HTTP_201_CREATED)


class AdminOrderViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    permission_classes = [IsAdmin]
    serializer_class = AdminOrderSerializer

    def get_queryset(self):
        qs = Order.objects.prefetch_related("items", "bookings").order_by("-created_at")
        params = self.request.query_params
        if s := params.get("status"):
            qs = qs.filter(status=s)
        if area := params.get("area"):
            qs = qs.filter(area_id=area)
        if q := params.get("q"):
            qs = qs.filter(Q(contact_phone__contains=q) | Q(contact_name__icontains=q))
        return qs

    @action(detail=True, methods=["patch"])
    def status(self, request, pk=None):
        order = self.get_object()
        logic.set_product_status(order, request.data.get("status"))
        return Response(AdminOrderSerializer(order).data)


class AdminBookingViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    permission_classes = [IsAdmin]
    serializer_class = AdminBookingSerializer

    def get_queryset(self):
        qs = Booking.objects.select_related("order").order_by("-created_at")
        if s := self.request.query_params.get("status"):
            qs = qs.filter(status=s)
        return qs


class AdminWarrantyViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    permission_classes = [IsAdmin]
    serializer_class = WarrantyClaimSerializer

    def get_queryset(self):
        qs = WarrantyClaim.objects.select_related("booking")
        if s := self.request.query_params.get("status"):
            qs = qs.filter(status=s)
        return qs

    @action(detail=True, methods=["post"])
    def approve(self, request, pk=None):
        claim = self.get_object()
        logic.approve_warranty_claim(claim, request.data.get("note", ""))
        return Response(WarrantyClaimSerializer(claim).data)

    @action(detail=True, methods=["post"])
    def reject(self, request, pk=None):
        claim = self.get_object()
        if claim.status != WarrantyClaim.Status.OPEN:
            return Response({"detail": "Claim already handled."}, status=status.HTTP_400_BAD_REQUEST)
        claim.status, claim.admin_note = WarrantyClaim.Status.REJECTED, request.data.get("note", "")
        claim.save(update_fields=["status", "admin_note"])
        return Response(WarrantyClaimSerializer(claim).data)


class AdminStatsView(APIView):
    permission_classes = [IsAdmin]

    def get(self, request):
        today = timezone.localdate()
        todays = Order.objects.filter(created_at__date=today)
        done = Order.objects.filter(status=Order.Status.COMPLETED)
        return Response(
            {
                "orders_today": todays.count(),
                "revenue_today": str(todays.exclude(status=Order.Status.CANCELLED).aggregate(s=Sum("total"))["s"] or 0),
                "revenue_completed": str(done.aggregate(s=Sum("total"))["s"] or 0),
                "orders_by_status": dict(Order.objects.values_list("status").annotate(n=Count("id"))),
                "bookings_by_status": dict(Booking.objects.values_list("status").annotate(n=Count("id"))),
                "open_warranty_claims": WarrantyClaim.objects.filter(status=WarrantyClaim.Status.OPEN).count(),
            }
        )


class VerifyArrivalView(generics.GenericAPIView):
    """Called by the provider service when a provider enters the customer's arrival code."""

    permission_classes = [IsInternal]
    authentication_classes = []

    def get(self, request, pk):
        booking = get_object_or_404(Booking, pk=pk)
        return Response({"ok": booking.arrival_code == request.query_params.get("code", "")})


class OrderPayableView(generics.GenericAPIView):
    permission_classes = [IsInternal]
    authentication_classes = []

    def get(self, request, pk):
        order = get_object_or_404(Order, pk=pk)
        payable = (
            order.payment_method == Order.PaymentMethod.ONLINE
            and order.payment_status == Order.PaymentStatus.UNPAID
            and order.status != Order.Status.CANCELLED
        )
        return Response({"user_id": order.user_id, "amount": str(order.total), "payable": payable})


class InternalOrganizationOrdersView(generics.GenericAPIView):
    """Completed orders of an organization in a period, for its monthly invoice."""

    permission_classes = [IsInternal]
    authentication_classes = []

    def get(self, request):
        p = request.query_params
        qs = Order.objects.filter(organization_id=p["organization_id"], status=Order.Status.COMPLETED,
                                  updated_at__date__gte=p["from"], updated_at__date__lte=p["to"])
        return Response([{"id": o.id, "number": o.number, "total": str(o.total), "date": o.updated_at.date().isoformat(),
                          "items": [b.service_name for b in o.bookings.all()] + [i.name for i in o.items.all()]} for o in qs])
