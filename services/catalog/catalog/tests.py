import pytest
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from catalog.models import Category, Service


def token(role):
    t = AccessToken()
    t["user_id"] = 1
    t["role"] = role
    return str(t)


@pytest.fixture
def client():
    return APIClient()


@pytest.fixture
def electrical():
    return Category.objects.create(kind="service", slug="electrical", name_en="Electrical", name_bn="ইলেকট্রিক্যাল")


def make_service(category, slug, price, **extra):
    return Service.objects.create(
        category=category, slug=slug, name_en=slug, name_bn=slug, base_price=price, **extra
    )


@pytest.mark.django_db
def test_anyone_can_list_active_services(client, electrical):
    make_service(electrical, "fan-repair", 300)
    make_service(electrical, "hidden", 300, is_active=False)
    res = client.get("/api/services/")
    assert res.status_code == 200
    assert [s["slug"] for s in res.data["results"]] == ["fan-repair"]


@pytest.mark.django_db
def test_filters_by_price_area_and_search(client, electrical):
    make_service(electrical, "cheap-fix", 200, area_ids=[1])
    make_service(electrical, "wiring-job", 900, area_ids=[2])
    make_service(electrical, "everywhere", 500)

    def slugs(query):
        return sorted(s["slug"] for s in client.get(f"/api/services/?{query}").data["results"])

    assert slugs("max_price=600") == ["cheap-fix", "everywhere"]
    assert slugs("area=2") == ["everywhere", "wiring-job"]
    assert slugs("q=wiring") == ["wiring-job"]
    assert client.get("/api/services/?min_price=abc").status_code == 400


@pytest.mark.django_db
def test_customer_cannot_create_but_admin_can(client, electrical):
    payload = {"category": electrical.id, "slug": "new", "name_en": "New", "name_bn": "নতুন", "base_price": "250.00"}

    client.credentials(HTTP_AUTHORIZATION=f"Bearer {token('customer')}")
    assert client.post("/api/services/", payload, format="json").status_code == 403

    client.credentials(HTTP_AUTHORIZATION=f"Bearer {token('admin')}")
    assert client.post("/api/services/", payload, format="json").status_code == 201


@pytest.mark.django_db
def test_service_rejects_product_category(client):
    shop = Category.objects.create(kind="product", slug="bulbs", name_en="Bulbs", name_bn="বাল্ব")
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {token('admin')}")
    res = client.post(
        "/api/services/",
        {"category": shop.id, "slug": "x", "name_en": "X", "name_bn": "X", "base_price": "1"},
        format="json",
    )
    assert res.status_code == 400


@pytest.mark.django_db(transaction=True)
def test_outbox_keeps_events_when_broker_is_down(settings, monkeypatch):
    """Shared outbox (shohor_common): a failed send is kept and relayed later."""
    from django.db import transaction
    from shohor_common import events
    from shohor_common.models import OutboxEvent

    settings.EVENTS_CAPTURE = False
    calls = []

    def broker_down(event, payload):
        raise ConnectionError("redis down")

    monkeypatch.setattr(events, "_send", broker_down)
    with transaction.atomic():
        events.publish("order.placed", {"order_id": 1})
    row = OutboxEvent.objects.get()
    assert row.sent_at is None and row.attempts == 1 and "redis down" in row.last_error

    monkeypatch.setattr(events, "_send", lambda event, payload: calls.append(event))
    assert events.relay(min_age_seconds=0) == 1
    assert calls == ["order.placed"] and OutboxEvent.objects.get().sent_at is not None

    with transaction.atomic():
        events.publish("order.placed", {"order_id": 2})
        transaction.set_rollback(True)
    assert OutboxEvent.objects.count() == 1  # rolled back with the change
