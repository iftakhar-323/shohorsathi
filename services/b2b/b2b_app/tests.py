from datetime import date, timedelta

import pytest
from django.utils import timezone
from rest_framework.test import APIClient
from shohor_common import internal
from shohor_common.testing import auth_client

from b2b_app import logic
from b2b_app.models import ContractVisit, Invoice, Organization

ORG = {"name": "Green View Apartments", "kind": "building", "contact_name": "Secretary", "contact_phone": "01711111111",
       "address_line": "Road 7", "area_id": 3, "area_name": "Mirpur", "units": 24}
ORDERS = [{"id": 5, "number": "SS261001-00005", "total": "1500.00", "date": "2026-09-10", "items": ["Pest control"]}]


@pytest.fixture(autouse=True)
def other_services(monkeypatch):
    def fake(service, path, **kw):
        if path.startswith("/api/internal/users/by-phone/01822222222"):
            return {"id": 8, "full_name": "Treasurer"}
        if path == "/api/internal/orders/":
            return ORDERS
        return None
    monkeypatch.setattr(internal, "get", fake)


@pytest.fixture
def secretary():
    return auth_client(user_id=7, name="Secretary", phone="01711111111")


def approved_org(client):
    org_id = client.post("/api/b2b/orgs/", ORG, format="json").data["id"]
    auth_client("admin").post(f"/api/admin/b2b/orgs/{org_id}/approve/")
    return org_id


@pytest.mark.django_db
def test_apply_add_member_and_membership_check(secretary):
    org_id = secretary.post("/api/b2b/orgs/", ORG, format="json").data["id"]
    check = {"organization_id": org_id, "user_id": 7}
    assert APIClient().post("/api/internal/b2b/membership/", check, format="json", HTTP_X_INTERNAL_TOKEN="dev-internal-token").data == {"ok": False}
    auth_client("admin").post(f"/api/admin/b2b/orgs/{org_id}/approve/")
    assert APIClient().post("/api/internal/b2b/membership/", check, format="json", HTTP_X_INTERNAL_TOKEN="dev-internal-token").data == {"ok": True}
    assert secretary.post(f"/api/b2b/orgs/{org_id}/members/", {"phone": "01899999999"}, format="json").status_code == 404
    assert secretary.post(f"/api/b2b/orgs/{org_id}/members/", {"phone": "01822222222"}, format="json").status_code == 201
    treasurer = auth_client(user_id=8)
    assert treasurer.get(f"/api/b2b/orgs/{org_id}/").data["stats"]["members"] == 2
    assert treasurer.post(f"/api/b2b/orgs/{org_id}/members/", {"phone": "01822222222"}, format="json").status_code == 403
    assert auth_client(user_id=99).get(f"/api/b2b/orgs/{org_id}/").status_code == 404


@pytest.mark.django_db
def test_contract_schedules_and_dispatches_visits(secretary, captured_events):
    org_id = approved_org(secretary)
    start = timezone.localdate() + timedelta(days=1)
    res = auth_client("admin").post(f"/api/admin/b2b/orgs/{org_id}/contracts/", {
        "title": "Monthly pest control", "category_slug": "pest-control", "visits_per_month": 1, "preferred_weekday": start.weekday(),
        "monthly_fee": "3000", "start_date": start.isoformat(), "end_date": (start + timedelta(days=364)).isoformat()}, format="json")
    assert res.status_code == 201
    assert 12 <= ContractVisit.objects.count() <= 13
    assert ContractVisit.objects.order_by("date").first().date == start  # the first visit is right at the start
    assert logic.dispatch_tomorrow() == 1
    assert captured_events[-1][0] == "b2b.visit_due"
    logic.apply_job_status({"source": "b2b_visit", "source_id": captured_events[-1][1]["visit_id"], "status": "completed", "provider_name": "Karim"})
    assert ContractVisit.objects.filter(status="completed").count() == 1


@pytest.mark.django_db
def test_invoice_has_contract_fee_and_orders_and_prints(secretary):
    org_id = approved_org(secretary)
    org = Organization.objects.get()
    from b2b_app.models import Contract

    Contract.objects.create(organization=org, title="Cleaning AMC", category_slug="cleaning", monthly_fee="5000",
                            start_date=date(2026, 1, 1), end_date=date(2026, 12, 31))
    inv = auth_client("admin").post(f"/api/admin/b2b/orgs/{org_id}/invoice/", {"period": "2026-09"}, format="json").data
    assert inv["total"] == "6500.00" and len(inv["lines"]) == 2 and inv["number"] == f"INV-{org_id:04d}-202609"
    html = secretary.get(f"/api/b2b/invoices/{inv['id']}/print/")
    assert html.status_code == 200 and b"Green View Apartments" in html.content
    auth_client("admin").post(f"/api/admin/b2b/invoices/{inv['id']}/mark-paid/", {"reference": "BANK-1"}, format="json")
    assert Invoice.objects.get().status == "paid"
    assert secretary.get(f"/api/b2b/orgs/{org_id}/").data["stats"]["unpaid_total"] == "0"
