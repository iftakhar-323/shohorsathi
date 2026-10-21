from decimal import Decimal

from django.conf import settings
from django.shortcuts import get_object_or_404
from rest_framework import serializers, status
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView
from shohor_common.internal import IsInternal
from shohor_common.permissions import IsAdmin

from . import logic
from .models import Account, Entry


class EntrySerializer(serializers.ModelSerializer):
    class Meta:
        model = Entry
        fields = ["kind", "delta", "reason", "ref", "created_at"]


def account_data(acc):
    return {
        "user_id": acc.user_id,
        "points": acc.points,
        "points_value": str(Decimal(acc.points) * Decimal(settings.POINT_VALUE_TAKA)),
        "wallet": str(acc.wallet),
        "referral_code": acc.referral_code,
        "referred": bool(acc.referred_by),
        "completed_orders": acc.completed_orders,
        "referrals": acc.referrals,
        "badges": acc.badges,
        "rules": {
            "points_per_100_taka": settings.POINTS_PER_100_TAKA,
            "point_value_taka": settings.POINT_VALUE_TAKA,
            "max_redeem_percent": settings.MAX_REDEEM_PERCENT,
            "referral_bonus": settings.REFERRAL_BONUS_TAKA,
            "referral_welcome": settings.REFERRAL_WELCOME_TAKA,
            "credit_note": "Closed-loop credit: spend on ShohorSathi only; not cash, not withdrawable or transferable.",
        },
    }


class MeView(APIView):
    def get(self, request):
        acc = logic.account(request.user.id)
        history = Entry.objects.filter(user_id=acc.user_id)[:50]
        return Response({**account_data(acc), "history": EntrySerializer(history, many=True).data})


class ReferralView(APIView):
    def post(self, request):
        acc = logic.apply_referral(request.user.id, request.data.get("code", ""))
        return Response(account_data(acc))



# ---- internal (order and payment services) -----------------------------------------------------

class InternalRedeemPoints(APIView):
    permission_classes = [IsInternal]
    authentication_classes = []

    def post(self, request):
        d = request.data
        discount = logic.redeem_points(int(d["user_id"]), int(d["order_id"]), int(d.get("points", 0)), d["subtotal"])
        return Response({"discount": str(discount)})


class InternalWalletPay(APIView):
    permission_classes = [IsInternal]
    authentication_classes = []

    def post(self, request):
        d = request.data
        logic.wallet_pay(int(d["user_id"]), int(d["order_id"]), d["amount"])
        return Response({"ok": True})


class InternalReverse(APIView):
    """Undo a checkout's redemption when the order could not be completed."""

    permission_classes = [IsInternal]
    authentication_classes = []

    def post(self, request):
        logic.order_cancelled({"order_id": int(request.data["order_id"])})
        return Response({"ok": True})



class AdminAccountsView(APIView):
    permission_classes = [IsAdmin]

    def get(self, request):
        qs = Account.objects.order_by("-points")
        if uid := request.query_params.get("user_id"):
            qs = qs.filter(user_id=uid)
        return Response([account_data(a) for a in qs[:100]])


class AdminAdjustView(APIView):
    """Goodwill credit or correction; the reason is kept in the ledger."""

    permission_classes = [IsAdmin]

    def post(self, request, user_id):
        reason = request.data.get("reason", "").strip()
        if not reason:
            raise ValidationError({"reason": "Give a reason."})
        ref = f"admin-{Entry.objects.count() + 1}"
        if points := int(request.data.get("points") or 0):
            logic.move(user_id, Entry.Kind.POINTS, points, f"admin:{reason[:30]}", ref)
        if wallet := Decimal(str(request.data.get("wallet") or 0)):
            logic.move(user_id, Entry.Kind.WALLET, wallet, f"admin:{reason[:30]}", ref)
        return Response(account_data(logic.account(user_id)))
