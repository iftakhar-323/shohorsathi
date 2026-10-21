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
def test_direct_bkash_and_nagad_payment(customer):
    res_bk = customer.post("/api/payments/initiate/", {"purpose": "order", "reference_id": 5, "gateway": "bkash"}, format="json")
    assert res_bk.status_code == 201
    assert "/api/payments/bkash/mock/" in res_bk.data["redirect_url"]
    tran_bk = res_bk.data["tran_id"]
    res_pay_bk = APIClient().post(
        "/api/payments/gateway/success/",
        {"tran_id": tran_bk, "amount": "660.00", "val_id": f"bkash-{tran_bk}", "card_type": "bKash"},
    )
    assert res_pay_bk.status_code == 302
    p_bk = Payment.objects.get(tran_id=tran_bk)
    assert p_bk.status == "held" and p_bk.method == "bKash"

    # Nagad direct
    PAYABLE["/api/internal/orders/6/payable/"] = {"user_id": 7, "amount": "450.00", "payable": True}
    res_ng = customer.post("/api/payments/initiate/", {"purpose": "order", "reference_id": 6, "gateway": "nagad"}, format="json")
    assert res_ng.status_code == 201
    assert "/api/payments/nagad/mock/" in res_ng.data["redirect_url"]
    tran_ng = res_ng.data["tran_id"]
    res_pay_ng = APIClient().post(
        "/api/payments/gateway/success/",
        {"tran_id": tran_ng, "amount": "450.00", "val_id": f"nagad-{tran_ng}", "card_type": "Nagad"},
    )
    assert res_pay_ng.status_code == 302
    p_ng = Payment.objects.get(tran_id=tran_ng)
    assert p_ng.status == "held" and p_ng.method == "Nagad"


@pytest.mark.django_db
def test_bkash_tokenized_agreement_and_auto_debit(customer, captured_events):
    # 1. Create agreement
    res_create = customer.post("/api/payments/agreements/bkash/create/", format="json")
    assert res_create.status_code == 200
    assert "agreement_url" in res_create.data

    # 2. Execute agreement
    agr_id = "AGR-TEST-1234"
    res_exec = customer.post("/api/payments/agreements/bkash/execute/", {"agreement_id": agr_id, "payer_reference": "01712345678"}, format="json")
    assert res_exec.status_code == 201
    assert res_exec.data["agreement_id"] == agr_id
    assert res_exec.data["status"] == "active"

    # 3. List my agreements
    res_list = customer.get("/api/payments/agreements/")
    assert res_list.status_code == 200
    results = res_list.data.get("results", res_list.data)
    assert len(results) == 1

    # 4. Auto-debit recurring charge via internal API
    PAYABLE["/api/internal/subscriptions/10/payable/"] = {"user_id": 7, "amount": "1200.00", "payable": True}
    res_charge = APIClient().post(
        "/api/internal/charge-agreement/",
        {"agreement_id": agr_id, "purpose": "subscription", "reference_id": 10, "amount": "1200.00"},
        format="json",
    )
    assert res_charge.status_code == 200
    assert res_charge.data["status"] == "held"
    assert res_charge.data["method"] == "bKash Auto-Debit"

    p = Payment.objects.get(purpose="subscription", reference_id=10)
    assert p.status == "held" and p.agreement.agreement_id == agr_id

    # 5. Cancel agreement
    res_cancel = customer.post(f"/api/payments/agreements/{res_exec.data['id']}/cancel/", format="json")
    assert res_cancel.status_code == 200 and res_cancel.data["status"] == "cancelled"


