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
