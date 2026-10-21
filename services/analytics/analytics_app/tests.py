from datetime import timedelta

import pytest
from django.utils import timezone
from shohor_common import internal
from shohor_common.testing import auth_client

from analytics_app import logic, tasks
from analytics_app.models import Fact


@pytest.fixture(autouse=True)
def areas(monkeypatch):
    monkeypatch.setattr(internal, "get", lambda service, path, **kw: [{"id": 3}] if kw.get("city") == "Dhaka" else [])


def feed():
    logic.record("order.placed", {"order_id": 1, "user_id": 7, "total": "1000", "area_id": 3, "area_name": "Mirpur"})
    logic.record("order.placed", {"order_id": 2, "user_id": 8, "total": "500", "area_id": 4, "area_name": "Agrabad"})
    logic.record("booking.created", {"source": "booking", "source_id": 1, "user_id": 7, "title": "ফ্যান মেরামত", "category_slug": "electrical",
                                     "amount": "300", "area_id": 3, "area_name": "Mirpur", "latitude": "23.81", "longitude": "90.41", "is_emergency": True})
    logic.record("order.status_changed", {"order_id": 1, "user_id": 7, "status": "completed", "total": "1000"})
    logic.record("order.status_changed", {"order_id": 2, "user_id": 8, "status": "confirmed", "total": "500"})  # ignored
    logic.record("job.completed", {"job_id": 1, "source": "booking", "amount": "300", "commission": "45"})
    logic.record("subscription.renewed", {"subscription_id": 1, "user_id": 7, "amount": "2800"})


@pytest.mark.django_db
def test_summary_numbers():
    feed()
    # user 8 ordered before the window: a returning customer
    Fact.objects.filter(event="order.placed", user_id=8).update(occurred_at=timezone.now() - timedelta(days=60))
    logic.record("order.placed", {"order_id": 3, "user_id": 8, "total": "200", "area_id": 4})
    s = auth_client("admin").get("/api/admin/analytics/summary/?days=30").data
    assert s["gmv"] == "1200.00" and s["revenue_completed"] == "1000.00" and s["commission"] == "45.00"
    assert s["customers_new"] == 1 and s["customers_returning"] == 1
    assert s["emergency_bookings"] == 1 and s["top_services"][0]["title"] == "ফ্যান মেরামত"
    assert s["subscriptions_renewed"] == 1


@pytest.mark.django_db
def test_city_filter_and_heatmap():
    feed()
    dhaka = auth_client("admin").get("/api/admin/analytics/summary/?city=Dhaka").data
    assert dhaka["orders"] == 1 and dhaka["gmv"] == "1000.00"
    heat = auth_client("admin").get("/api/admin/analytics/heatmap/").data
    assert heat == [{"lat": 23.81, "lng": 90.41, "n": 1}]
    assert auth_client().get("/api/admin/analytics/summary/").status_code == 403


def test_task_per_event():
    assert "analytics.booking.created" in {t.name for t in tasks.TASKS.values()}


def at(fact, days_ago):
    Fact.objects.filter(pk=fact.pk).update(occurred_at=timezone.now() - timedelta(days=days_ago))


@pytest.mark.django_db
def test_forecast_uses_same_weekday_history(settings):
    settings.JOBS_PER_PROVIDER_DAY = 2
    tomorrow = timezone.localdate() + timedelta(days=1)
    for week in range(1, 9):  # 4 AC bookings on tomorrow's weekday, every week for 8 weeks
        for _ in range(4):
            f = logic.record("booking.created", {"source": "booking", "source_id": 1, "user_id": 1, "category_slug": "ac", "amount": "800"})
            at(f, (timezone.localdate() - (tomorrow - timedelta(weeks=week))).days)
    res = auth_client("admin").get("/api/admin/analytics/forecast/").data
    ac = res[0]
    assert ac["category"] == "ac"
    first = ac["days"][0]
    assert first["date"] == tomorrow.isoformat()
    assert 3 <= first["expected"] <= 5 and first["providers_needed"] >= 2
    assert ac["days"][1]["expected"] == 0  # nothing on the other weekdays


@pytest.mark.django_db
def test_churn_flags_customers_gone_quiet_and_winback(captured_events):
    for days_ago in (100, 80, 60):  # ordered every 20 days, then stopped 60 days ago
        at(logic.record("order.placed", {"order_id": 1, "user_id": 7, "total": "500"}), days_ago)
    at(logic.record("order.placed", {"order_id": 2, "user_id": 8, "total": "500"}), 10)  # recent one-timer: fine
    at(logic.record("order.placed", {"order_id": 3, "user_id": 9, "total": "500"}), 400)  # lost, not at risk
    admin = auth_client("admin")
    risky = admin.get("/api/admin/analytics/churn/").data
    assert [c["user_id"] for c in risky] == [7]
    assert risky[0]["usual_gap_days"] == 20 and risky[0]["risk"] == "high"
    assert admin.post("/api/admin/analytics/churn/winback/", {"user_ids": [7]}, format="json").data == {"sent": 1}
    assert ("analytics.winback", {"user_id": 7, "message": ""}) in captured_events


@pytest.mark.django_db
def test_fraud_signals():
    for i in range(3):
        logic.record("order.status_changed", {"order_id": i, "user_id": 5, "status": "cancelled", "total": "100"})
    for i in range(5):
        logic.record("order.placed", {"order_id": 10 + i, "user_id": 6, "total": "100"})
    for u in (20, 21, 22, 23):
        logic.record("booking.created", {"source": "booking", "source_id": u, "user_id": u, "category_slug": "ac",
                                         "latitude": "23.810001", "longitude": "90.410001"})
    logic.record("order.placed", {"order_id": 99, "user_id": 30, "total": "25000", "payment_method": "cod"})
    kinds = {f["kind"]: f for f in auth_client("admin").get("/api/admin/analytics/fraud/").data}
    assert kinds["cancel_abuse"]["user_ids"] == [5]
    assert kinds["order_burst"]["user_ids"] == [6] and kinds["order_burst"]["severity"] == "high"
    assert kinds["shared_location"]["user_ids"] == [20, 21, 22, 23]
    assert kinds["big_first_cod"]["user_ids"] == [30]
    assert auth_client("customer").get("/api/admin/analytics/fraud/").status_code == 403


@pytest.mark.django_db
def test_revenue_includes_sponsored_listings():
    logic.record("job.completed", {"job_id": 1, "source": "booking", "amount": "1000", "commission": "150"})
    logic.record("listing.sponsored", {"item_type": "service", "slug": "ac-cleaning", "name": "AC", "fee": "2000"})
    r = auth_client("admin").get("/api/admin/analytics/revenue/").data
    assert r == {"days": 30, "commission": "150.00", "sponsored_listings": "2000.00", "total": "2150.00"}
