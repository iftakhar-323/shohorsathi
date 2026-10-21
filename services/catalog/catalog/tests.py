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


@pytest.mark.django_db
def test_bangla_fuzzy_search(client, electrical):
    Service.objects.create(
        category=electrical, slug="electrician-service", name_en="Electrician Visit",
        name_bn="ইলেকট্রিশিয়ান সার্ভিস", base_price=500
    )
    res = client.get("/api/services/?q=ইলেকট্রিশিয়ান")
    assert res.status_code == 200
    assert any(s["slug"] == "electrician-service" for s in res.data["results"])


@pytest.mark.django_db
def test_group_deal_join(client, electrical):
    from datetime import timedelta
    from django.utils import timezone
    from catalog.models import GroupDeal
    srv = make_service(electrical, "ac-clean-pkg", 1000)
    deal = GroupDeal.objects.create(
        title_en="Dhanmondi AC Clean", title_bn="ধানমন্ডি এসি ক্লিন",
        service=srv, target_participants=2, discount_percent=20,
        expires_at=timezone.now() + timedelta(days=7),
    )
    assert deal.discounted_price == 800
    assert not deal.is_locked_in

    client.credentials(HTTP_AUTHORIZATION=f"Bearer {token('customer')}")
    res = client.post(f"/api/group-deals/{deal.id}/join/")
    assert res.status_code == 200
    assert res.data["joined"] is True
    assert res.data["current_participants"] == 1

    t2 = AccessToken()
    t2["user_id"] = 2
    t2["role"] = "customer"
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {str(t2)}")
    res2 = client.post(f"/api/group-deals/{deal.id}/join/")
    assert res2.status_code == 200
    assert res2.data["is_locked_in"] is True
    listed = client.get("/api/group-deals/").data["results"][0]
    assert listed["joined"] is True and "participant_user_ids" not in listed

    deal.expires_at = timezone.now() - timedelta(minutes=1)
    deal.save()
    assert client.get("/api/group-deals/").data["results"] == []
    assert client.post(f"/api/group-deals/{deal.id}/join/").status_code in (400, 404)


@pytest.mark.django_db
def test_seasonal_packages(client):
    from datetime import timedelta
    from django.utils import timezone
    from catalog.models import SeasonalPackage
    today = timezone.localdate()
    SeasonalPackage.objects.create(
        title_en="Eid Special", title_bn="ঈদ স্পেশাল",
        season="eid", tagline_bn="ঈদ উপলক্ষে অফার",
        service_slugs=["clean-1", "clean-2"], discount_percent=25,
        active_from=today - timedelta(days=1), active_until=today + timedelta(days=10)
    )
    SeasonalPackage.objects.create(title_en="Old", title_bn="পুরনো", season="eid", active_from=today - timedelta(days=60),
                                   active_until=today - timedelta(days=30))
    res = client.get("/api/seasonal-packages/?season=eid")
    assert res.status_code == 200
    assert len(res.data["results"]) == 1  # the finished one is hidden
    assert res.data["results"][0]["discount_percent"] == 25


@pytest.mark.django_db
def test_internal_group_deal_discount(client, electrical):
    from datetime import timedelta
    from django.utils import timezone
    from catalog.models import GroupDeal
    srv = make_service(electrical, "fan-fix", 400)
    deal = GroupDeal.objects.create(title_en="x", title_bn="x", service=srv, target_participants=2, discount_percent=15,
                                    participant_user_ids=[5], current_participants=1, expires_at=timezone.now() + timedelta(days=3))
    url = "/api/internal/group-deals/discount/"
    hdr = {"HTTP_X_INTERNAL_TOKEN": "dev-internal-token"}
    assert client.get(url, {"user_id": 5, "slug": "fan-fix"}).status_code == 403
    assert client.get(url, {"user_id": 5, "slug": "fan-fix"}, **hdr).data["percent"] == 0  # not filled yet
    deal.participant_user_ids, deal.current_participants = [5, 6], 2
    deal.save()
    assert client.get(url, {"user_id": 5, "slug": "fan-fix"}, **hdr).data["percent"] == 15
    assert client.get(url, {"user_id": 9, "slug": "fan-fix"}, **hdr).data["percent"] == 0


@pytest.mark.django_db
def test_sponsored_listing_comes_first_and_records_the_fee(client, electrical, captured_events):
    old = make_service(electrical, "old-fan", 300)
    make_service(electrical, "new-fan", 300)
    admin = APIClient()
    admin.credentials(HTTP_AUTHORIZATION=f"Bearer {token('admin')}")
    assert client.get("/api/services/").data["results"][0]["slug"] == "new-fan"

    res = admin.post("/api/services/old-fan/sponsor/", {"days": 7, "fee": "1500", "sponsor_name": "Rahim Electric"}, format="json")
    assert res.status_code == 201
    listed = client.get("/api/services/").data["results"]
    assert listed[0]["slug"] == "old-fan" and listed[0]["is_sponsored"] is True and listed[1]["is_sponsored"] is False
    assert ("listing.sponsored", {"item_type": "service", "slug": "old-fan", "name": old.name_bn, "fee": "1500.00", "sponsor": "Rahim Electric"}) in captured_events
    assert admin.get("/api/catalog/sponsored/").data["results"][0]["sponsor_name"] == "Rahim Electric"

    customer = APIClient()
    customer.credentials(HTTP_AUTHORIZATION=f"Bearer {token('customer')}")
    assert customer.post("/api/services/new-fan/sponsor/", {"days": 7, "fee": "0", "sponsor_name": "x"}, format="json").status_code == 403


@pytest.mark.django_db
def test_admin_saves_uploaded_photo_path(electrical):
    admin = APIClient()
    admin.credentials(HTTP_AUTHORIZATION=f"Bearer {token('admin')}")
    res = admin.post("/api/services/", {"category": electrical.id, "slug": "fan-fix", "name_en": "Fan", "name_bn": "ফ্যান",
                                        "base_price": "300", "image_url": "/media/public/catalog/2026/10/a.jpg"}, format="json")
    assert res.status_code == 201, res.data
    assert res.data["image_url"] == "/media/public/catalog/2026/10/a.jpg"
