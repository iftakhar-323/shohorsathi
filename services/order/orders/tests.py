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
        "warranty_days": 7, "is_active": True, "emergency_available": True,
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


@pytest.mark.django_db
def test_online_order_waits_for_payment(customer, captured_events):
    service_item = fill_cart(customer)
    details = {str(service_item): {"scheduled_date": timezone.localdate().isoformat(), "slot": "09-11"}}
    order = customer.post("/api/orders/", {**ADDRESS, "service_details": details, "payment_method": "online"}, format="json").data
    assert [e for e, _ in captured_events] == ["order.placed"]
    from rest_framework.test import APIClient

    payable = APIClient().get(f"/api/internal/orders/{order['id']}/payable/", HTTP_X_INTERNAL_TOKEN="dev-internal-token").data
    assert payable == {"user_id": 7, "amount": "660.00", "payable": True}
    logic.payment_succeeded({"purpose": "order", "reference_id": order["id"], "amount": "660.00"})
    assert Order.objects.get().payment_status == "paid"
    assert [e for e, _ in captured_events][-1] == "booking.created"
    logic.payment_succeeded({"purpose": "order", "reference_id": order["id"], "amount": "660.00"})
    assert [e for e, _ in captured_events].count("booking.created") == 1


@pytest.mark.django_db
def test_emergency_booking_today_with_surcharge(customer):
    item = customer.post("/api/cart/items/", {"item_type": "service", "slug": "fan-repair"}, format="json").data["id"]
    tomorrow = (timezone.localdate() + timedelta(days=1)).isoformat()
    bad = customer.post("/api/orders/", {**ADDRESS, "service_details": {str(item): {"scheduled_date": tomorrow, "slot": "09-11", "is_emergency": True}}}, format="json")
    assert bad.status_code == 400
    ok = customer.post("/api/orders/", {**ADDRESS, "service_details": {str(item): {"scheduled_date": timezone.localdate().isoformat(), "slot": "09-11", "is_emergency": True}}}, format="json")
    booking = ok.data["bookings"][0]
    assert booking["is_emergency"] and booking["surcharge"] == "75.00" and booking["price"] == "375.00"
    assert ok.data["total"] == "375.00"


@pytest.mark.django_db
def test_points_discount_and_wallet_payment(customer, monkeypatch, captured_events):
    calls = []

    def fake_post(service, path, body):
        calls.append(path)
        if path.endswith("redeem-points/"):
            return 200, {"discount": "100"}
        if path.endswith("wallet-pay/"):
            return 200, {"ok": True}
        return 200, {}

    monkeypatch.setattr(internal, "post", fake_post)
    item = fill_cart(customer)
    details = {str(item): {"scheduled_date": timezone.localdate().isoformat(), "slot": "09-11"}}
    res = customer.post("/api/orders/", {**ADDRESS, "service_details": details, "redeem_points": 100, "payment_method": "wallet"}, format="json")
    assert res.status_code == 201, res.data
    assert res.data["discount"] == "100.00" and res.data["total"] == "560.00" and res.data["payment_status"] == "paid"
    assert "booking.created" in [e for e, _ in captured_events]  # wallet-paid orders go straight to providers


@pytest.mark.django_db
def test_wallet_short_rolls_back_and_reverses(customer, monkeypatch):
    calls = []

    def fake_post(service, path, body):
        calls.append(path)
        return (400, {"wallet": ["Not enough"]}) if path.endswith("wallet-pay/") else (200, {"discount": "50"})

    monkeypatch.setattr(internal, "post", fake_post)
    fill_cart(customer)
    item = customer.get("/api/cart/").data["items"][-1]["id"]
    details = {str(item): {"scheduled_date": timezone.localdate().isoformat(), "slot": "09-11"}}
    res = customer.post("/api/orders/", {**ADDRESS, "service_details": details, "redeem_points": 50, "payment_method": "wallet"}, format="json")
    assert res.status_code == 400 and not Order.objects.exists()
    assert calls[-1] == "/api/internal/loyalty/reverse/"
    assert customer.get("/api/cart/").data["items"]  # cart kept


@pytest.mark.django_db
def test_overdue_product_orders_flagged(customer):
    order_id = place_order(customer).data["id"]
    Order.objects.filter(pk=order_id).update(created_at=timezone.now() - timedelta(days=6))
    admin = auth_client("admin", user_id=1)
    assert admin.get("/api/admin/order-stats/").data["overdue_deliveries"] == 1
    assert [o["id"] for o in admin.get("/api/admin/orders/?overdue=1").data["results"]] == [order_id]


@pytest.mark.django_db
def test_user_deleted_redacts_orders_but_keeps_totals(customer):
    from rest_framework.test import APIClient

    from orders.tasks import user_deleted

    order_id = place_order(customer).data["id"]
    export = APIClient().get("/api/internal/export/7/", HTTP_X_INTERNAL_TOKEN="dev-internal-token").data
    assert export[0]["address"].startswith("Road 1")
    user_deleted({"user_id": 7})
    order = Order.objects.get(pk=order_id)
    assert (order.contact_name, order.contact_phone, order.address_line) == ("Deleted user", "", "") and order.total > 0


@pytest.mark.django_db
def test_prefer_female_reaches_job_and_provider_phone_window(customer, captured_events):
    item = customer.post("/api/cart/items/", {"item_type": "service", "slug": "fan-repair"}, format="json").data["id"]
    details = {str(item): {"scheduled_date": timezone.localdate().isoformat(), "slot": "09-11", "prefer_female": True}}
    booking = customer.post("/api/orders/", {**ADDRESS, "service_details": details}, format="json").data["bookings"][0]
    assert [p for e, p in captured_events if e == "booking.created"][0]["required_gender"] == "female"
    logic.apply_job_status({"source": "booking", "source_id": booking["id"], "status": "accepted", "provider_id": 5, "provider_name": "Rina", "provider_phone": "01811111111"})
    assert customer.get(f"/api/bookings/{booking['id']}/").data["provider_phone"] == "01811111111"
    logic.apply_job_status({"source": "booking", "source_id": booking["id"], "status": "completed"})
    assert customer.get(f"/api/bookings/{booking['id']}/").data["provider_phone"] == ""
