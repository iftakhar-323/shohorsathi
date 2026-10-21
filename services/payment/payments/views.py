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
from .models import Payment, PaymentAgreement, RefundRequest


class PaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Payment
        fields = ["id", "tran_id", "purpose", "reference_id", "amount", "currency", "gateway", "status", "method",
                  "agreement", "refunded_amount", "created_at", "paid_at", "released_at"]


class PaymentAgreementSerializer(serializers.ModelSerializer):
    class Meta:
        model = PaymentAgreement
        fields = ["id", "gateway", "agreement_id", "payer_reference", "status", "created_at", "cancelled_at"]
        read_only_fields = ["id", "gateway", "agreement_id", "status", "created_at", "cancelled_at"]


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
        gateway_name = request.data.get("gateway") or request.data.get("method")
        payment, url = logic.initiate(user, purpose, int(request.data.get("reference_id", 0)), gateway_name=gateway_name)
        return Response({"tran_id": payment.tran_id, "amount": str(payment.amount), "redirect_url": url, "gateway": payment.gateway}, status=status.HTTP_201_CREATED)


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


class MockBkashPage(APIView):
    permission_classes = [AllowAny]

    def get(self, request, tran_id):
        p = get_object_or_404(Payment, tran_id=tran_id)
        api = settings.PUBLIC_API_URL
        hidden = (f'<input type="hidden" name="tran_id" value="{escape(p.tran_id)}">'
                  f'<input type="hidden" name="amount" value="{p.amount}">')
        html = f"""<!doctype html><html lang="bn"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>bKash Payment</title><style>body{{font-family:system-ui;background:#fdf2f4;display:flex;justify-content:center;padding:40px 16px}}
main{{background:#fff;border:2px solid #D12053;border-radius:20px;padding:28px;max-width:380px;width:100%}}
button{{width:100%;height:48px;border-radius:12px;font-size:16px;font-weight:600;margin-top:10px;border:0;cursor:pointer}}
.pay{{background:#D12053;color:#fff}}.fail{{background:#fde8e7;color:#b42318}}</style></head><body><main>
<div style="display:flex;align-items:center;gap:8px"><span style="background:#D12053;color:#fff;padding:4px 8px;border-radius:6px;font-weight:700">bKash</span><h3 style="margin:0;color:#D12053">বিকাশ পেমেন্ট</h3></div>
<h1 style="margin:16px 0 8px">৳ {p.amount}</h1>
<p style="color:#666;font-size:14px">ট্রানজ্যাকশন আইডি: {escape(p.tran_id)}</p>
<form method="post" action="{api}/api/payments/gateway/success/">{hidden}<input type="hidden" name="val_id" value="bkash-{escape(p.tran_id)}">
<input type="hidden" name="card_type" value="bKash">
<button class="pay" type="submit">বিকাশ দিয়ে নিশ্চিত করুন</button></form>
<form method="post" action="{api}/api/payments/gateway/cancel/">{hidden}<button type="submit">বাতিল করুন</button></form>
</main></body></html>"""
        return HttpResponse(html)


class MockNagadPage(APIView):
    permission_classes = [AllowAny]

    def get(self, request, tran_id):
        p = get_object_or_404(Payment, tran_id=tran_id)
        api = settings.PUBLIC_API_URL
        hidden = (f'<input type="hidden" name="tran_id" value="{escape(p.tran_id)}">'
                  f'<input type="hidden" name="amount" value="{p.amount}">')
        html = f"""<!doctype html><html lang="bn"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Nagad Payment</title><style>body{{font-family:system-ui;background:#fff8f0;display:flex;justify-content:center;padding:40px 16px}}
main{{background:#fff;border:2px solid #F7941D;border-radius:20px;padding:28px;max-width:380px;width:100%}}
button{{width:100%;height:48px;border-radius:12px;font-size:16px;font-weight:600;margin-top:10px;border:0;cursor:pointer}}
.pay{{background:#F7941D;color:#fff}}.fail{{background:#fde8e7;color:#b42318}}</style></head><body><main>
<div style="display:flex;align-items:center;gap:8px"><span style="background:#F7941D;color:#fff;padding:4px 8px;border-radius:6px;font-weight:700">নগদ</span><h3 style="margin:0;color:#F7941D">নগদ পেমেন্ট</h3></div>
<h1 style="margin:16px 0 8px">৳ {p.amount}</h1>
<p style="color:#666;font-size:14px">ট্রানজ্যাকশন আইডি: {escape(p.tran_id)}</p>
<form method="post" action="{api}/api/payments/gateway/success/">{hidden}<input type="hidden" name="val_id" value="nagad-{escape(p.tran_id)}">
<input type="hidden" name="card_type" value="Nagad">
<button class="pay" type="submit">নগদ দিয়ে পেমেন্ট করুন</button></form>
<form method="post" action="{api}/api/payments/gateway/cancel/">{hidden}<button type="submit">বাতিল করুন</button></form>
</main></body></html>"""
        return HttpResponse(html)


class MockAgreementPage(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        user_id = request.query_params.get("user_id", "1")
        phone = request.query_params.get("phone", "01700000000")
        agr_id = f"AGR-{secrets.token_hex(6).upper()}"
        api = settings.PUBLIC_API_URL
        customer_url = settings.CUSTOMER_WEB_URL
        html = f"""<!doctype html><html lang="bn"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>bKash Tokenized Auto-Debit</title><style>body{{font-family:system-ui;background:#fdf2f4;display:flex;justify-content:center;padding:40px 16px}}
main{{background:#fff;border:2px solid #D12053;border-radius:20px;padding:28px;max-width:400px;width:100%}}
button{{width:100%;height:48px;border-radius:12px;font-size:16px;font-weight:600;margin-top:10px;border:0;cursor:pointer}}
.pay{{background:#D12053;color:#fff}}</style></head><body><main>
<div style="display:flex;align-items:center;gap:8px"><span style="background:#D12053;color:#fff;padding:4px 8px;border-radius:6px;font-weight:700">bKash</span><h3 style="margin:0;color:#D12053">বিকাশ অটো-ডেবিট চুক্তি</h3></div>
<p style="margin:16px 0 8px;font-size:15px;color:#333">ShohorSathi সাবস্ক্রিপশন অটো-রিনিউ করার জন্য বিকাশ অ্যাকাউন্ট অনুমোদন করুন।</p>
<p style="background:#f6f8f5;padding:10px;border-radius:8px;font-size:13px;color:#555">অ্যাকাউন্ট: {escape(phone)}<br>অ্যাগ্রিমেন্ট আইডি: {agr_id}</p>
<a href="{customer_url}/subscriptions?agreement_id={agr_id}"><button class="pay">অনুমোদন সম্পন্ন করুন (Approve)</button></a>
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


class PaymentAgreementViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    serializer_class = PaymentAgreementSerializer

    def get_queryset(self):
        return PaymentAgreement.objects.filter(user_id=self.request.user.id)

    @action(detail=False, methods=["post"], url_path="bkash/create")
    def create_bkash(self, request):
        user = {"id": request.user.id, "phone": request.auth.get("phone", "")}
        data = logic.create_agreement(user)
        return Response(data, status=status.HTTP_200_OK)

    @action(detail=False, methods=["post"], url_path="bkash/execute")
    def execute_bkash(self, request):
        user = {"id": request.user.id, "phone": request.auth.get("phone", "")}
        agreement_id = request.data.get("agreement_id")
        payer_reference = request.data.get("payer_reference", "")
        if not agreement_id:
            return Response({"agreement_id": ["Required."]}, status=status.HTTP_400_BAD_REQUEST)
        agreement = logic.execute_agreement(user, agreement_id, payer_reference)
        return Response(PaymentAgreementSerializer(agreement).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"], url_path="cancel")
    def cancel_agreement(self, request, pk=None):
        agreement = logic.cancel_agreement(request.user.id, pk)
        return Response(PaymentAgreementSerializer(agreement).data)


class InternalChargeAgreementView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        agreement_id = request.data.get("agreement_id")
        purpose = request.data.get("purpose")
        reference_id = int(request.data.get("reference_id", 0))
        amount = request.data.get("amount")
        payment = logic.charge_agreement(agreement_id, purpose, reference_id, amount)
        return Response({
            "payment_id": payment.id,
            "tran_id": payment.tran_id,
            "status": payment.status,
            "amount": str(payment.amount),
            "method": payment.method,
        })

