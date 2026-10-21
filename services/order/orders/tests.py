from datetime import timedelta

import pytest
from django.utils import timezone
from shohor_common import internal
from shohor_common.testing import auth_client

from orders import logic
from orders.models import Booking, Order, WarrantyClaim

CATALOG = {
    "/api/services/fan-repair/": {
        "slug": "fan-repair", "name_bn": "ফ্যান মেরামত", "base_price": "300.00", "category_slug": "electrical",
        "warranty_days": 7, "is_active": True,
    },
    "/api/products/led-bulb/": {"slug": "led-bulb", "name_bn": "এলইডি বাল্ব", "price": "180.00", "stock": 5, "is_active": True},
}


@pytest.fixture(autouse=True)
def fake_catalog(monkeypatch):
    monkeypatch.setattr(internal, "get", lambda service, path, **kw: CATALOG.get(path))


@pytest.fixture
def customer():
    return auth_client("customer", user_id=7)


ADDRESS = {
    "contact_name": "Rahim", "contact_phone": "01712345678", "address_line": "Road 1, House 2",
    "area_id": 3, "area_name": "Mirpur",
}


def fill_cart(client):
    client.post("/api/cart/items/", {"item_type": "product", "slug": "led-bulb", "quantity": 2}, format="json")
    return client.post("/api/cart/items/", {"item_type": "service", "slug": "fan-repair"}, format="json").data["id"]


def place_order(client):
    service_item = fill_cart(client)
    details = {str(service_item): {"scheduled_date": timezone.localdate().isoformat(), "slot": "09-11"}}
    return client.post("/api/orders/", {**ADDRESS, "service_details": details}, format="json")


@pytest.mark.django_db
def test_cart_prices_come_from_catalog(customer):
    fill_cart(customer)
    cart = customer.get("/api/cart/").data
    assert cart["subtotal"] == "660.00"


@pytest.mark.django_db
def test_cannot_add_more_than_stock(customer):
    res = customer.post("/api/cart/items/", {"item_type": "product", "slug": "led-bulb", "quantity": 9}, format="json")
    assert res.status_code == 400


@pytest.mark.django_db
def test_unknown_item_rejected(customer):
    res = customer.post("/api/cart/items/", {"item_type": "service", "slug": "nope"}, format="json")
    assert res.status_code == 400


@pytest.mark.django_db
def test_checkout_creates_order_booking_and_events(customer, captured_events):
    res = place_order(customer)
    assert res.status_code == 201, res.data
    assert res.data["total"] == "660.00"
    assert len(res.data["bookings"]) == 1
    assert customer.get("/api/cart/").data["items"] == []
    names = [e for e, _ in captured_events]
    assert names == ["order.placed", "booking.created"]
    booking_event = captured_events[1][1]
    assert booking_event["source"] == "booking" and booking_event["category_slug"] == "electrical"
    assert "arrival_code" not in booking_event


@pytest.mark.django_db
def test_checkout_requires_service_schedule(customer):
    fill_cart(customer)
    res = customer.post("/api/orders/", ADDRESS, format="json")
    assert res.status_code == 400


@pytest.mark.django_db
def test_other_users_cannot_see_order(customer):
    order_id = place_order(customer).data["id"]
    assert auth_client("customer", user_id=8).get(f"/api/orders/{order_id}/").status_code == 404


@pytest.mark.django_db
def test_job_status_flows_into_booking_and_order(customer):
    order_id = place_order(customer).data["id"]
    booking = Booking.objects.get(order_id=order_id)
    logic.apply_job_status({"source": "booking", "source_id": booking.id, "status": "accepted",
                            "provider_id": 55, "provider_name": "Karim", "provider_phone": "01811111111"})
    booking.refresh_from_db()
    assert booking.status == "confirmed" and booking.provider_name == "Karim"
    assert Order.objects.get(pk=order_id).status == "confirmed"

    logic.apply_job_status({"source": "booking", "source_id": booking.id, "status": "completed"})
    order = Order.objects.get(pk=order_id)
    # products not delivered yet, so the order is not complete
    assert order.status == "confirmed"

    admin = auth_client("admin", user_id=1)
    assert admin.patch(f"/api/admin/orders/{order_id}/status/", {"status": "on_the_way"}, format="json").status_code == 200
    admin.patch(f"/api/admin/orders/{order_id}/status/", {"status": "delivered"}, format="json")
    order.refresh_from_db()
    assert order.status == "completed" and order.payment_status == "paid"
    tracking = customer.get(f"/api/orders/{order_id}/tracking/").data
    assert [e["status"] for e in tracking["events"]][0] == "pending"


@pytest.mark.django_db
def test_cancel_order_while_pending(customer, captured_events):
    order_id = place_order(customer).data["id"]
    captured_events.clear()
    res = customer.post(f"/api/orders/{order_id}/cancel/")
    assert res.data["status"] == "cancelled"
    assert [e for e, _ in captured_events] == ["booking.cancelled", "order.status_changed"]


@pytest.mark.django_db
def test_reschedule_rejects_past_date(customer):
    booking_id = place_order(customer).data["bookings"][0]["id"]
    yesterday = (timezone.localdate() - timedelta(days=1)).isoformat()
    res = customer.patch(f"/api/bookings/{booking_id}/reschedule/", {"scheduled_date": yesterday, "slot": "09-11"}, format="json")
    assert res.status_code == 400


@pytest.mark.django_db
def test_warranty_claim_within_window(customer, captured_events):
    booking_id = place_order(customer).data["bookings"][0]["id"]
    assert customer.post(f"/api/bookings/{booking_id}/warranty/", {"description": "x"}, format="json").status_code == 400

    Booking.objects.filter(pk=booking_id).update(status="completed", completed_at=timezone.now(), provider_id=55)
    res = customer.post(f"/api/bookings/{booking_id}/warranty/", {"description": "Fan stopped again"}, format="json")
    assert res.status_code == 201

    captured_events.clear()
    admin = auth_client("admin", user_id=1)
    admin.post(f"/api/admin/warranty-claims/{res.data['id']}/approve/")
    event, payload = captured_events[0]
    assert event == "booking.created" and payload["source"] == "warranty" and payload["amount"] == "0"
    assert payload["preferred_provider_id"] == 55

    logic.apply_job_status({"source": "warranty", "source_id": res.data["id"], "status": "completed"})
    assert WarrantyClaim.objects.get().status == "resolved"


@pytest.mark.django_db
def test_warranty_expired(customer):
    booking_id = place_order(customer).data["bookings"][0]["id"]
    Booking.objects.filter(pk=booking_id).update(status="completed", completed_at=timezone.now() - timedelta(days=8))
    res = customer.post(f"/api/bookings/{booking_id}/warranty/", {"description": "x"}, format="json")
    assert res.status_code == 400


@pytest.mark.django_db
def test_verify_arrival_needs_internal_token(customer):
    booking = Booking.objects.get(pk=place_order(customer).data["bookings"][0]["id"])
    from rest_framework.test import APIClient

    url = f"/api/internal/bookings/{booking.id}/verify-arrival/?code={booking.arrival_code}"
    assert APIClient().get(url).status_code == 403
    ok = APIClient().get(url, HTTP_X_INTERNAL_TOKEN="dev-internal-token")
    assert ok.data == {"ok": True}


@pytest.mark.django_db
def test_customer_cannot_use_admin_endpoints(customer):
    assert customer.get("/api/admin/orders/").status_code == 403
