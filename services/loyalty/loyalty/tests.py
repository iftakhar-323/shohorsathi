from decimal import Decimal

import pytest
from rest_framework.test import APIClient
from shohor_common.testing import auth_client

from loyalty import logic
from loyalty.models import Account

INTERNAL = {"HTTP_X_INTERNAL_TOKEN": "dev-internal-token"}


@pytest.mark.django_db
def test_points_on_completed_order_once():
    logic.order_completed({"order_id": 1, "user_id": 7, "total": "1250.00"})
    logic.order_completed({"order_id": 1, "user_id": 7, "total": "1250.00"})  # replay
    acc = Account.objects.get(user_id=7)
    assert acc.points == 12 and acc.completed_orders == 1 and "first_order" in acc.badges


@pytest.mark.django_db
def test_referral_pays_after_first_order():
    referrer = logic.account(1)
    me = auth_client(user_id=2)
    assert me.post("/api/loyalty/referral/", {"code": "nope"}, format="json").status_code == 400
    assert me.post("/api/loyalty/referral/", {"code": referrer.referral_code}, format="json").status_code == 200
    assert me.post("/api/loyalty/referral/", {"code": referrer.referral_code}, format="json").status_code == 400
    logic.order_completed({"order_id": 9, "user_id": 2, "total": "500"})
    assert Account.objects.get(user_id=1).wallet == 100 and Account.objects.get(user_id=2).wallet == 50
    assert "referrer" in Account.objects.get(user_id=1).badges


@pytest.mark.django_db
def test_redeem_capped_and_reversed_on_cancel():
    logic.move(7, "points", 500, "seed", "x")
    res = APIClient().post("/api/internal/loyalty/redeem-points/", {"user_id": 7, "order_id": 3, "points": 400, "subtotal": "1000"}, format="json", **INTERNAL)
    assert res.data == {"discount": "200"}  # 20% of 1000
    assert Account.objects.get(user_id=7).points == 300
    logic.order_cancelled({"order_id": 3, "user_id": 7, "status": "cancelled"})
    assert Account.objects.get(user_id=7).points == 500
    assert APIClient().post("/api/internal/loyalty/redeem-points/", {"user_id": 7, "order_id": 3, "points": 1, "subtotal": "10"}, format="json").status_code == 403


@pytest.mark.django_db
def test_credit_pay_and_return_on_cancel():
    me = auth_client(user_id=7)
    logic.move(7, "wallet", Decimal("500"), "promo", "eid")
    assert me.post("/api/loyalty/topups/", {"amount": "500"}, format="json").status_code == 404  # no cash top-ups
    short = APIClient().post("/api/internal/loyalty/wallet-pay/", {"user_id": 7, "order_id": 4, "amount": "900"}, format="json", **INTERNAL)
    assert short.status_code == 400
    APIClient().post("/api/internal/loyalty/wallet-pay/", {"user_id": 7, "order_id": 4, "amount": "300"}, format="json", **INTERNAL)
    logic.order_cancelled({"order_id": 4, "user_id": 7, "status": "cancelled"})
    assert Account.objects.get(user_id=7).wallet == 500
    history = me.get("/api/loyalty/me/").data["history"]
    assert [h["reason"] for h in history][:2] == ["pay_order_reversed", "pay_order"]


@pytest.mark.django_db
def test_subscription_bonus_and_admin_adjust():
    logic.subscription_bonus({"user_id": 7, "subscription_id": 1}, renewal=False)
    logic.subscription_bonus({"user_id": 7, "subscription_id": 2}, renewal=True)
    acc = Account.objects.get(user_id=7)
    assert acc.points == 40 and "loyal_subscriber" in acc.badges
    admin = auth_client("admin")
    assert admin.post("/api/admin/loyalty/accounts/7/adjust/", {"wallet": "100"}, format="json").status_code == 400
    res = admin.post("/api/admin/loyalty/accounts/7/adjust/", {"wallet": "100", "reason": "Late provider"}, format="json")
    assert Decimal(res.data["wallet"]) == 100
