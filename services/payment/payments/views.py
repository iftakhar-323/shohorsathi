from html import escape
from urllib.parse import urlencode

from django.conf import settings
from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import get_object_or_404
from rest_framework import mixins, serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from shohor_common.permissions import IsAdmin

from . import logic
from .models import Payment, RefundRequest


class PaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Payment
        fields = ["id", "tran_id", "purpose", "reference_id", "amount", "currency", "gateway", "status", "method",
                  "refunded_amount", "created_at", "paid_at", "released_at"]


class AdminPaymentSerializer(PaymentSerializer):
    class Meta(PaymentSerializer.Meta):
        fields = PaymentSerializer.Meta.fields + ["user_id", "bank_tran_id", "val_id"]


class RefundSerializer(serializers.ModelSerializer):
    tran_id = serializers.CharField(source="payment.tran_id", read_only=True)
    purpose = serializers.CharField(source="payment.purpose", read_only=True)
    reference_id = serializers.IntegerField(source="payment.reference_id", read_only=True)

    class Meta:
        model = RefundRequest
        fields = ["id", "tran_id", "purpose", "reference_id", "amount", "reason", "status", "automatic", "admin_note", "gateway_ref", "created_at"]
        read_only_fields = ["id", "status", "automatic", "admin_note", "gateway_ref", "created_at"]


class InitiateView(APIView):
    def post(self, request):
        purpose = request.data.get("purpose")
        if purpose not in Payment.Purpose.values:
            return Response({"purpose": ["Unknown purpose."]}, status=status.HTTP_400_BAD_REQUEST)
        user = {"id": request.user.id, "name": request.auth.get("name", ""), "phone": request.auth.get("phone", "")}
        payment, url = logic.initiate(user, purpose, int(request.data.get("reference_id", 0)))
        return Response({"tran_id": payment.tran_id, "amount": str(payment.amount), "redirect_url": url}, status=status.HTTP_201_CREATED)


def result_redirect(payment, fallback_status):
    params = {"tran_id": payment.tran_id if payment else "", "status": payment.status if payment else fallback_status,
              "purpose": payment.purpose if payment else "", "reference_id": payment.reference_id if payment else ""}
    return HttpResponseRedirect(f"{settings.CUSTOMER_WEB_URL}/payment/result?{urlencode(params)}")


class GatewayReturnView(APIView):
    """The gateway sends the customer's browser back here (form POST) after paying, failing or cancelling."""

    permission_classes = [AllowAny]
    authentication_classes = []
    parser_classes = [FormParser, MultiPartParser, JSONParser]
    outcome = "success"

    def post(self, request):
        data = request.data
        if self.outcome == "success":
            payment = logic.confirm(data)
        else:
            logic.mark_unpaid(data.get("tran_id", ""), Payment.Status.FAILED if self.outcome == "fail" else Payment.Status.CANCELLED)
            payment = Payment.objects.filter(tran_id=data.get("tran_id", "")).first()
        return result_redirect(payment, self.outcome)


class IpnView(APIView):
    """Server-to-server notification; the source of truth even if the customer closes the browser."""

    permission_classes = [AllowAny]
    authentication_classes = []
    parser_classes = [FormParser, MultiPartParser, JSONParser]

    def post(self, request):
        payment = logic.confirm(request.data)
        return Response({"status": payment.status if payment else "unknown"})


class MockGatewayPage(APIView):
    """Development stand-in for the SSLCommerz checkout page."""

    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request, tran_id):
        if settings.PAYMENT_GATEWAY != "mock":
            return HttpResponse(status=404)
        p = get_object_or_404(Payment, tran_id=tran_id)
        api = settings.PUBLIC_API_URL
        hidden = (f'<input type="hidden" name="tran_id" value="{escape(p.tran_id)}">'
                  f'<input type="hidden" name="amount" value="{p.amount}">')
        html = f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Test payment</title><style>body{{font-family:system-ui;background:#f6f8f5;display:flex;justify-content:center;padding:40px 16px}}
main{{background:#fff;border:1px solid #dce5df;border-radius:20px;padding:28px;max-width:380px;width:100%}}
button{{width:100%;height:48px;border-radius:12px;font-size:16px;font-weight:600;margin-top:10px;border:0;cursor:pointer}}
.pay{{background:#17784a;color:#fff}}.fail{{background:#fde8e7;color:#b42318}}</style></head><body><main>
<p style="color:#4a5a52;margin:0">Test gateway — no real money moves</p><h1 style="margin:8px 0">৳ {p.amount}</h1>
<p>Transaction {escape(p.tran_id)}</p>
<form method="post" action="{api}/api/payments/gateway/success/">{hidden}<input type="hidden" name="val_id" value="mock-{escape(p.tran_id)}">
<label>Pay with <select name="card_type"><option>bKash</option><option>Nagad</option><option>VISA</option></select></label>
<button class="pay" type="submit">Pay</button></form>
<form method="post" action="{api}/api/payments/gateway/fail/">{hidden}<button class="fail" type="submit">Fail payment</button></form>
<form method="post" action="{api}/api/payments/gateway/cancel/">{hidden}<button type="submit">Cancel</button></form>
</main></body></html>"""
        return HttpResponse(html)


class MyPaymentViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    serializer_class = PaymentSerializer
    lookup_field = "tran_id"

    def get_queryset(self):
        qs = Payment.objects.filter(user_id=self.request.user.id)
        if p := self.request.query_params.get("purpose"):
            qs = qs.filter(purpose=p, reference_id=self.request.query_params.get("reference_id"))
        return qs

    @action(detail=True, methods=["post"], url_path="refund-request")
    def refund_request(self, request, tran_id=None):
        payment = self.get_object()
        if payment.status not in (Payment.Status.HELD, Payment.Status.RELEASED):
            return Response({"payment": ["Only paid payments can be refunded."]}, status=status.HTTP_400_BAD_REQUEST)
        if payment.refunds.filter(status=RefundRequest.Status.REQUESTED).exists():
            return Response({"payment": ["A refund request is already open."]}, status=status.HTTP_400_BAD_REQUEST)
        data = RefundSerializer(data={"amount": request.data.get("amount") or logic.refundable(payment), "reason": request.data.get("reason", "")})
        data.is_valid(raise_exception=True)
        row = RefundRequest.objects.create(payment=payment, user_id=payment.user_id, **data.validated_data)
        return Response(RefundSerializer(row).data, status=status.HTTP_201_CREATED)


class AdminPaymentViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    permission_classes = [IsAdmin]
    serializer_class = AdminPaymentSerializer

    def get_queryset(self):
        qs = Payment.objects.all()
        params = self.request.query_params
        if s := params.get("status"):
            qs = qs.filter(status=s)
        if p := params.get("purpose"):
            qs = qs.filter(purpose=p)
        if t := params.get("q"):
            qs = qs.filter(tran_id__icontains=t)
        return qs

    @action(detail=False)
    def balances(self, request):
        return Response(logic.balances())


class AdminRefundViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    permission_classes = [IsAdmin]
    serializer_class = RefundSerializer

    def get_queryset(self):
        qs = RefundRequest.objects.select_related("payment")
        if s := self.request.query_params.get("status"):
            qs = qs.filter(status=s)
        return qs

    @action(detail=True, methods=["post"])
    def approve(self, request, pk=None):
        row = self.get_object()
        if row.status != RefundRequest.Status.REQUESTED:
            return Response({"detail": "Already handled."}, status=status.HTTP_400_BAD_REQUEST)
        if amount := request.data.get("amount"):
            row.amount = amount
        return Response(RefundSerializer(logic.refund(row, request.data.get("note", ""))).data)

    @action(detail=True, methods=["post"])
    def reject(self, request, pk=None):
        row = self.get_object()
        if row.status != RefundRequest.Status.REQUESTED:
            return Response({"detail": "Already handled."}, status=status.HTTP_400_BAD_REQUEST)
        row.status, row.admin_note = RefundRequest.Status.REJECTED, request.data.get("note", "")
        row.save(update_fields=["status", "admin_note"])
        return Response(RefundSerializer(row).data)
