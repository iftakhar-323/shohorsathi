from datetime import date

import pytest
from shohor_common import internal
from shohor_common.testing import auth_client

from providers import logic
from providers.models import Earning, Job, Provider

REGISTRATION = {
    "provider_type": "electrician", "skills": ["electrical"], "area_ids": [3], "nid_number": "1234567890",
    "photo_url": "/media/p.jpg", "nid_front_url": "/media/n.jpg", "payout_method": "bkash", "payout_account": "01811111111",
}
BOOKING = {
    "source": "booking", "source_id": 10, "booking_id": 10, "user_id": 7, "title": "Fan repair",
    "category_slug": "electrical", "area_id": 3, "area_name": "Mirpur", "address_line": "Road 1",
    "customer_name": "Rahim", "customer_phone": "01712345678", "scheduled_date": date.today().isoformat(),
    "slot": "20-22", "amount": "1000.00", "is_emergency": False,
}


@pytest.fixture
def provider_client():
    return auth_client("customer", user_id=50, name="Karim", phone="01811111111")


@pytest.fixture
def approved(provider_client):
    provider_client.post("/api/providers/register/", REGISTRATION, format="json")
    provider = Provider.objects.get(user_id=50)
    logic.review_provider(provider, "approve")
    return provider


@pytest.mark.django_db
def test_register_uses_token_identity(provider_client):
    res = provider_client.post("/api/providers/register/", REGISTRATION, format="json")
    assert res.status_code == 201
    assert res.data["full_name"] == "Karim" and res.data["status"] == "pending"
    assert provider_client.post("/api/providers/register/", REGISTRATION, format="json").status_code == 400


@pytest.mark.django_db
def test_home_chef_needs_kitchen_photos(provider_client):
    res = provider_client.post("/api/providers/register/", {**REGISTRATION, "provider_type": "home_chef"}, format="json")
    assert res.status_code == 400 and "kitchen_photo_urls" in res.data


@pytest.mark.django_db
def test_pending_provider_cannot_see_jobs(provider_client):
    provider_client.post("/api/providers/register/", REGISTRATION, format="json")
    assert provider_client.get("/api/providers/jobs/?tab=available").status_code == 403


@pytest.mark.django_db
def test_admin_approval_emits_event(provider_client, captured_events):
    provider_client.post("/api/providers/register/", REGISTRATION, format="json")
    pid = Provider.objects.get().id
    admin = auth_client("admin")
    assert admin.post(f"/api/admin/providers/{pid}/reject/", {}, format="json").status_code == 400
    res = admin.post(f"/api/admin/providers/{pid}/approve/")
    assert res.data["status"] == "approved"
    assert captured_events[-1] == ("provider.approved", {"user_id": 50, "provider_id": pid})


@pytest.mark.django_db
def test_full_job_flow(provider_client, approved, captured_events, monkeypatch):
    logic.create_job(BOOKING)
    available = provider_client.get("/api/providers/jobs/?tab=available").data["results"]
    assert len(available) == 1 and "customer_phone" not in available[0]
    job_id = available[0]["id"]

    res = provider_client.post(f"/api/providers/jobs/{job_id}/accept/")
    assert res.data["status"] == "accepted" and res.data["customer_phone"] == "01712345678"
    provider_client.patch(f"/api/providers/jobs/{job_id}/status/", {"status": "on_the_way"}, format="json")

    monkeypatch.setattr(internal, "get", lambda service, path, **kw: {"ok": kw.get("code") == "1234"})
    wrong = provider_client.patch(f"/api/providers/jobs/{job_id}/status/", {"status": "working", "arrival_code": "0000"}, format="json")
    assert wrong.status_code == 400
    provider_client.patch(f"/api/providers/jobs/{job_id}/status/", {"status": "working", "arrival_code": "1234"}, format="json")
    done = provider_client.patch(
        f"/api/providers/jobs/{job_id}/status/", {"status": "completed", "photos": ["/media/after.jpg"]}, format="json"
    )
    assert done.data["status"] == "completed" and done.data["after_photos"] == ["/media/after.jpg"]

    earning = Earning.objects.get()
    assert (earning.gross, earning.commission, earning.net) == (1000, 150, 850)
    statuses = [p["status"] for e, p in captured_events if e == "job.status_changed"]
    assert statuses == ["accepted", "on_the_way", "working", "completed"]
    assert captured_events[-1][0] == "job.completed"

    summary = provider_client.get("/api/providers/earnings/").data["summary"]
    assert summary["pending"] == "850.00"
    payout = provider_client.post("/api/providers/payouts/")
    assert payout.status_code == 201 and payout.data["amount"] == "850.00"
    assert provider_client.post("/api/providers/payouts/").status_code == 400

    admin = auth_client("admin")
    admin.post(f"/api/admin/payouts/{payout.data['id']}/mark-paid/", {"reference": "TX123"}, format="json")
    assert Earning.objects.get().status == "paid"


@pytest.mark.django_db
def test_job_outside_area_is_hidden(provider_client, approved):
    logic.create_job({**BOOKING, "area_id": 99})
    assert provider_client.get("/api/providers/jobs/?tab=available").data["count"] == 0


@pytest.mark.django_db
def test_two_providers_cannot_take_same_job(approved):
    other = auth_client("customer", user_id=51, name="Other", phone="01822222222")
    other.post("/api/providers/register/", REGISTRATION, format="json")
    logic.review_provider(Provider.objects.get(user_id=51), "approve")
    job = logic.create_job(BOOKING)
    logic.accept(job, approved)
    from rest_framework.exceptions import ValidationError

    with pytest.raises(ValidationError):
        logic.accept(job, Provider.objects.get(user_id=51))


@pytest.mark.django_db
def test_reject_returns_job_to_pool(provider_client, approved, captured_events):
    job = logic.create_job(BOOKING)
    provider_client.post(f"/api/providers/jobs/{job.id}/accept/")
    provider_client.post(f"/api/providers/jobs/{job.id}/reject/")
    job.refresh_from_db()
    assert job.status == "open" and job.provider is None
    assert captured_events[-1][1]["status"] == "open"


@pytest.mark.django_db
def test_warranty_job_goes_to_previous_provider(approved):
    job = logic.create_job({**BOOKING, "source": "warranty", "source_id": 1, "preferred_provider_id": 50})
    assert job.status == "assigned" and job.provider == approved


@pytest.mark.django_db
def test_admin_assign_and_suggestions(approved):
    job = logic.create_job(BOOKING)
    admin = auth_client("admin")
    suggestions = admin.get(f"/api/admin/jobs/{job.id}/suggestions/").data
    assert [p["id"] for p in suggestions] == [approved.id]
    res = admin.post(f"/api/admin/jobs/{job.id}/assign/", {"provider_id": approved.id}, format="json")
    assert res.data["status"] == "assigned"


@pytest.mark.django_db
def test_cancel_from_booking_event(approved):
    job = logic.create_job(BOOKING)
    logic.cancel_from_source({"source": "booking", "source_id": 10})
    job.refresh_from_db()
    assert job.status == "cancelled"


@pytest.mark.django_db
def test_rating_updates_average_and_badges(approved):
    for _ in range(10):
        logic.apply_review({"provider_user_id": 50, "rating": 5})
    approved.refresh_from_db()
    assert approved.rating_avg == 5 and "top_rated" in approved.badges


@pytest.mark.django_db
def test_customer_reviews_completed_job_once(approved):
    job = logic.create_job(BOOKING)
    customer = auth_client("customer", user_id=7)
    body = {"source": "booking", "source_id": 10, "rating": 4, "comment": "Good"}
    assert customer.post("/api/providers/reviews/", body, format="json").status_code == 400  # not completed yet
    Job.objects.filter(pk=job.pk).update(status="completed", provider=approved)
    assert auth_client("customer", user_id=8).post("/api/providers/reviews/", body, format="json").status_code == 400
    assert customer.post("/api/providers/reviews/", body, format="json").status_code == 201
    assert customer.post("/api/providers/reviews/", body, format="json").status_code == 400
    approved.refresh_from_db()
    assert approved.rating_avg == 4 and approved.rating_count == 1
    public = auth_client().get(f"/api/providers/public/{approved.id}/reviews/").data
    assert public["results"][0]["comment"] == "Good"


@pytest.mark.django_db
def test_emergency_job_alerts_online_providers(approved, captured_events):
    Provider.objects.filter(pk=approved.pk).update(is_online=True)
    logic.create_job({**BOOKING, "is_emergency": True})
    event, payload = captured_events[-1]
    assert event == "emergency.raised" and payload["provider_user_ids"] == [50]


@pytest.mark.django_db
def test_customer_tracking_location(provider_client, approved):
    job = logic.create_job(BOOKING)
    logic.accept(job, approved)
    provider_client.patch(f"/api/providers/jobs/{job.id}/status/", {"status": "on_the_way"}, format="json")
    provider_client.post("/api/providers/me/location/", {"latitude": "23.8", "longitude": "90.4"}, format="json")
    customer = auth_client("customer", user_id=7)
    res = customer.get("/api/providers/tracking/booking/10/")
    assert res.data["available"] is True and res.data["latitude"] == "23.800000"
    assert auth_client("customer", user_id=8).get("/api/providers/tracking/booking/10/").status_code == 404


@pytest.mark.django_db
def test_weekly_payouts(approved):
    job = logic.create_job(BOOKING)
    Job.objects.filter(pk=job.pk).update(status="working", provider=approved)
    job.refresh_from_db()
    logic.advance(job, approved, "completed")
    assert logic.weekly_payouts() == 1


@pytest.mark.django_db
def test_custom_request_job_uses_quoted_platform_fee(approved):
    from providers.tasks import custom_request_accepted

    custom_request_accepted({**BOOKING, "request_id": 5, "amount": "7500.00", "commission_override": "700.00"})
    job = Job.objects.get(source="custom_request")
    Job.objects.filter(pk=job.pk).update(status="working", provider=approved)
    job.refresh_from_db()
    logic.advance(job, approved, "completed")
    assert Earning.objects.get().net == 6800
