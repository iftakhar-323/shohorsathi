from decimal import Decimal

import pytest
from rest_framework.test import APIClient
from shohor_common import internal
from shohor_common.testing import auth_client

from payments import logic
from payments.models import Payment, RefundRequest

PAYABLE = {"/api/internal/orders/5/payable/": {"user_id": 7, "amount": "660.00", "payable": True}}


@pytest.fixture(autouse=True)
def owners(monkeypatch):
    monkeypatch.setattr(internal, "get", lambda service, path, **kw: PAYABLE.get(path))


@pytest.fixture
def customer():
    return auth_client("customer", user_id=7, name="Rahim", phone="01712345678")


def start(customer):
    return customer.post("/api/payments/initiate/", {"purpose": "order", "reference_id": 5}, format="json")


def pay(tran_id, amount="660.00", val_id=None):
    return APIClient().post(
        "/api/payments/gateway/success/",
        {"tran_id": tran_id, "amount": amount, "val_id": val_id or f"mock-{tran_id}", "card_type": "bKash"},
    )


@pytest.mark.django_db
def test_amount_comes_from_owner_service(customer):
    res = start(customer)
    assert res.status_code == 201 and res.data["amount"] == "660.00"
    assert "/api/payments/mock/" in res.data["redirect_url"]


@pytest.mark.django_db
def test_cannot_pay_someone_elses_order():
    assert start(auth_client("customer", user_id=8)).status_code == 403


@pytest.mark.django_db
def test_success_holds_in_escrow_and_emits(customer, captured_events):
    tran = start(customer).data["tran_id"]
    res = pay(tran)
    assert res.status_code == 302 and "status=held" in res["Location"]
    p = Payment.objects.get()
    assert p.status == "held" and p.method == "bKash"
    assert logic.balances()["escrow"] == "660.00"
    assert captured_events[-1] == ("payment.succeeded", {"payment_id": p.id, "user_id": 7, "purpose": "order", "reference_id": 5, "amount": "660.00"})
    # replayed callback / IPN is ignored
    APIClient().post("/api/payments/gateway/ipn/", {"tran_id": tran, "val_id": f"mock-{tran}", "amount": "660.00"})
    assert [e for e, _ in captured_events].count("payment.succeeded") == 1


@pytest.mark.django_db
def test_tampered_amount_or_val_id_fails(customer):
    tran = start(customer).data["tran_id"]
    pay(tran, amount="1.00")
    assert Payment.objects.get().status == "failed"
    tran2 = start(customer).data["tran_id"]
    pay(tran2, val_id="forged")
    assert Payment.objects.get(tran_id=tran2).status == "failed"


@pytest.mark.django_db
def test_cannot_pay_twice(customer):
    pay(start(customer).data["tran_id"])
    assert start(customer).status_code == 400


@pytest.mark.django_db
def test_release_on_order_completed(customer):
    pay(start(customer).data["tran_id"])
    logic.on_status("order", {"order_id": 5, "status": "completed"}, done={"completed"}, cancelled={"cancelled"})
    assert Payment.objects.get().status == "released"
    assert logic.balances() == {"escrow": "0.00", "settled": "660.00", "refunds": "0.00"}


@pytest.mark.django_db
def test_auto_refund_on_cancel(customer, captured_events):
    pay(start(customer).data["tran_id"])
    logic.on_status("order", {"order_id": 5, "status": "cancelled"}, done={"completed"}, cancelled={"cancelled"})
    p = Payment.objects.get()
    assert p.status == "refunded" and p.refunded_amount == Decimal("660.00")
    assert captured_events[-1][0] == "payment.refunded" and captured_events[-1][1]["automatic"] is True


@pytest.mark.django_db
def test_refund_request_partial_approved_by_admin(customer):
    tran = start(customer).data["tran_id"]
    pay(tran)
    res = customer.post(f"/api/payments/mine/{tran}/refund-request/", {"reason": "Provider broke a tile", "amount": "200"}, format="json")
    assert res.status_code == 201
    admin = auth_client("admin")
    done = admin.post(f"/api/admin/refunds/{res.data['id']}/approve/", {"note": "ok"}, format="json")
    assert done.data["status"] == "refunded"
    p = Payment.objects.get()
    assert p.status == "held" and p.refunded_amount == 200
    assert RefundRequest.objects.get().gateway_ref.startswith("MOCKREF")


@pytest.mark.django_db
def test_fail_and_cancel_returns(customer):
    tran = start(customer).data["tran_id"]
    res = APIClient().post("/api/payments/gateway/cancel/", {"tran_id": tran})
    assert "status=cancelled" in res["Location"]


@pytest.mark.django_db
def test_mock_page_renders(customer):
    tran = start(customer).data["tran_id"]
    page = APIClient().get(f"/api/payments/mock/{tran}/")
    assert page.status_code == 200 and b"660.00" in page.content


@pytest.mark.django_db
def test_wallet_topup_is_released_at_once(monkeypatch):
    PAYABLE["/api/internal/loyalty/topups/3/payable/"] = {"user_id": 7, "amount": "500.00", "payable": True}
    client = auth_client("customer", user_id=7)
    tran = client.post("/api/payments/initiate/", {"purpose": "wallet_topup", "reference_id": 3}, format="json").data["tran_id"]
    res = pay(tran, amount="500.00")
    assert "status=released" in res["Location"]
