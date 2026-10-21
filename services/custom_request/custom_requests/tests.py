from datetime import date, timedelta

import pytest
from shohor_common.testing import auth_client

from custom_requests import logic
from custom_requests.models import CustomRequest

REQUEST = {
    "service_type": "Wall painting for 2 rooms", "description": "Two bedrooms, 12x10 ft each",
    "area_id": 3, "area_name": "Mirpur", "address_line": "Road 1", "preferred_date": date.today().isoformat(),
    "budget_min": "5000", "budget_max": "8000",
}
QUOTE = {"labor": "4000", "materials": "2500", "transport": "300", "platform_fee": "700", "timeline_days": 2,
         "category_slug": "painting"}


@pytest.fixture
def customer():
    return auth_client("customer", user_id=7, name="Rahim", phone="01712345678")


@pytest.fixture
def admin():
    return auth_client("admin")


def submit(customer):
    return customer.post("/api/custom-requests/", REQUEST, format="json").data["id"]


@pytest.mark.django_db
def test_submit_uses_token_contact(customer):
    rid = submit(customer)
    req = CustomRequest.objects.get(pk=rid)
    assert (req.customer_name, req.customer_phone, req.status) == ("Rahim", "01712345678", "submitted")


@pytest.mark.django_db
def test_budget_and_date_validation(customer):
    bad = customer.post("/api/custom-requests/", {**REQUEST, "budget_min": "9000"}, format="json")
    assert bad.status_code == 400
    past = (date.today() - timedelta(days=1)).isoformat()
    assert customer.post("/api/custom-requests/", {**REQUEST, "preferred_date": past}, format="json").status_code == 400


@pytest.mark.django_db
def test_quote_accept_creates_job_event(customer, admin, captured_events):
    rid = submit(customer)
    admin.post(f"/api/admin/custom-requests/{rid}/review/")
    res = admin.patch(f"/api/admin/custom-requests/{rid}/quote/", QUOTE, format="json")
    assert res.data["status"] == "quote_sent" and res.data["quote"]["total"] == "7500.00"

    accepted = customer.post(f"/api/custom-requests/{rid}/accept/").data
    assert accepted["final_amount"] == "7500.00" and accepted["advance_amount"] == "750.00"
    event, payload = [e for e in captured_events if e[0] == "custom_request.accepted"][0]
    assert payload["category_slug"] == "painting" and payload["commission_override"] == "700.00"


@pytest.mark.django_db
def test_single_counter_offer_round(customer, admin):
    rid = submit(customer)
    admin.patch(f"/api/admin/custom-requests/{rid}/quote/", QUOTE, format="json")
    assert customer.post(f"/api/custom-requests/{rid}/counter/", {"amount": "6500"}, format="json").data["status"] == "countered"
    admin.patch(f"/api/admin/custom-requests/{rid}/quote/", {**QUOTE, "labor": "3500"}, format="json")
    again = customer.post(f"/api/custom-requests/{rid}/counter/", {"amount": "6000"}, format="json")
    assert again.status_code == 400
    detail = admin.get(f"/api/admin/custom-requests/{rid}/").data
    assert len(detail["quotes"]) == 2 and detail["quote"]["total"] == "7000.00"


@pytest.mark.django_db
def test_cannot_accept_without_quote(customer):
    rid = submit(customer)
    assert customer.post(f"/api/custom-requests/{rid}/accept/").status_code == 400


@pytest.mark.django_db
def test_decline_needs_reason(customer, admin):
    rid = submit(customer)
    assert admin.post(f"/api/admin/custom-requests/{rid}/decline/", {}, format="json").status_code == 400
    res = admin.post(f"/api/admin/custom-requests/{rid}/decline/", {"reason": "Unsafe work"}, format="json")
    assert res.data["status"] == "rejected"


@pytest.mark.django_db
def test_job_events_update_request(customer, admin):
    rid = submit(customer)
    admin.patch(f"/api/admin/custom-requests/{rid}/quote/", QUOTE, format="json")
    customer.post(f"/api/custom-requests/{rid}/accept/")
    logic.apply_job_status({"source": "custom_request", "source_id": rid, "status": "accepted", "provider_name": "Karim"})
    assert customer.get(f"/api/custom-requests/{rid}/").data["status"] == "provider_assigned"
    logic.apply_job_status({"source": "custom_request", "source_id": rid, "status": "completed"})
    assert CustomRequest.objects.get(pk=rid).status == "completed"


@pytest.mark.django_db
def test_privacy_and_admin_only(customer):
    rid = submit(customer)
    assert auth_client("customer", user_id=8).get(f"/api/custom-requests/{rid}/").status_code == 404
    assert customer.get("/api/admin/custom-requests/").status_code == 403


@pytest.mark.django_db
def test_trends(customer, admin):
    submit(customer)
    customer.post("/api/custom-requests/", {**REQUEST, "service_type": "wall painting for 2 rooms"}, format="json")
    assert admin.get("/api/admin/custom-requests/trends/").data[0] == {"name": "wall painting for 2 rooms", "count": 2}
