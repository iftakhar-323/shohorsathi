"""End-to-end smoke test of the Phase 1 flow through the gateway, with real Celery events.

Needs the stack running (docker compose up) and `docker compose exec catalog python manage.py seed_catalog`.
Usage: python3 scripts/e2e_phase1.py [http://localhost:8088]
"""
import json
import subprocess
import sys
import time
import urllib.request
from datetime import date

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8088"
STAMP = str(int(time.time()))[-8:]


def call(method, path, token=None, body=None, expect=None):
    req = urllib.request.Request(BASE + path, method=method, data=json.dumps(body).encode() if body is not None else None)
    req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req) as res:
            status, data = res.status, res.read()
    except urllib.error.HTTPError as e:
        status, data = e.code, e.read()
    parsed = json.loads(data) if data else None
    if expect and status != expect:
        raise SystemExit(f"{method} {path} -> {status} (expected {expect}): {parsed}")
    return parsed


def otp(phone):
    call("POST", "/api/auth/otp/request/", body={"phone": phone, "purpose": "register"}, expect=200)
    logs = subprocess.run(["docker", "compose", "logs", "auth"], capture_output=True, text=True).stdout
    return [line for line in logs.splitlines() if f"OTP for {phone}" in line][-1].split()[-1]


def register(phone, name):
    res = call("POST", "/api/auth/register/", body={"phone": phone, "full_name": name, "password": "strong-pass-123", "otp": otp(phone)}, expect=201)
    return res


def wait_for(fn, what, timeout=15):
    end = time.time() + timeout
    while time.time() < end:
        value = fn()
        if value:
            return value
        time.sleep(0.5)
    raise SystemExit(f"timed out waiting for {what}")


def step(msg):
    print(f"  ✓ {msg}")


def main():
    customer_phone, provider_phone, admin_phone = f"017{STAMP}", f"018{STAMP}", f"019{STAMP}"

    customer = register(customer_phone, "E2E Customer")["access"]
    step("customer registered with OTP")

    subprocess.run(
        ["docker", "compose", "exec", "-T", "-e", "DJANGO_SUPERUSER_PASSWORD=admin-pass-123", "auth", "python", "manage.py",
         "createsuperuser", "--noinput", "--phone", admin_phone, "--full_name", "E2E Admin"],
        check=True, capture_output=True,
    )
    admin = call("POST", "/api/auth/login/", body={"phone": admin_phone, "password": "admin-pass-123"}, expect=200)["access"]
    area = call("POST", "/api/admin/areas/", admin, {"name_en": f"Area {STAMP}", "name_bn": "এলাকা"}, expect=201)
    step(f"admin created area {area['id']}")

    provider_tokens = register(provider_phone, "E2E Provider")
    provider = provider_tokens["access"]
    call("POST", "/api/providers/register/", provider, {
        "provider_type": "electrician", "skills": ["electrical"], "area_ids": [area["id"]], "nid_number": "1234567890",
        "photo_url": "/media/x.jpg", "nid_front_url": "/api/media/1/download/", "payout_method": "bkash",
        "payout_account": provider_phone,
    }, expect=201)
    pending = call("GET", "/api/admin/providers/?status=pending", admin, expect=200)["results"]
    pid = [p for p in pending if p["phone"] == provider_phone][0]["id"]
    call("POST", f"/api/admin/providers/{pid}/approve/", admin, expect=200)
    step("provider applied and admin approved")

    def provider_role():
        tokens = call("POST", "/api/auth/token/refresh/", body={"refresh": provider_tokens["refresh"]}, expect=200)
        provider_tokens.update(tokens)
        import base64
        claims = json.loads(base64.urlsafe_b64decode(tokens["access"].split(".")[1] + "=="))
        return claims["role"] == "provider"

    wait_for(provider_role, "auth to apply provider.approved")
    provider = provider_tokens["access"]
    step("provider.approved event changed the user's role (seen on token refresh)")

    item = call("POST", "/api/cart/items/", customer, {"item_type": "service", "slug": "electrician-visit"}, expect=201)
    call("POST", "/api/cart/items/", customer, {"item_type": "product", "slug": "led-bulb-12w", "quantity": 2}, expect=201)
    order = call("POST", "/api/orders/", customer, {
        "contact_name": "E2E Customer", "contact_phone": customer_phone, "address_line": "Road 1",
        "area_id": area["id"], "area_name": area["name_en"],
        "service_details": {str(item["id"]): {"scheduled_date": date.today().isoformat(), "slot": "20-22", "problem_description": "Fan"}},
    }, expect=201)
    booking = order["bookings"][0]
    step(f"order {order['number']} placed, total ৳{order['total']}")

    job = wait_for(
        lambda: next(iter(call("GET", "/api/providers/jobs/?tab=available", provider, expect=200)["results"]), None),
        "booking.created to reach the provider inbox",
    )
    step("job appeared in the provider's inbox")

    call("POST", f"/api/providers/jobs/{job['id']}/accept/", provider, expect=200)
    wait_for(lambda: call("GET", f"/api/orders/{order['id']}/", customer)["bookings"][0]["status"] == "confirmed", "booking confirmed")
    step("provider accepted; customer's booking is confirmed")

    call("PATCH", f"/api/providers/jobs/{job['id']}/status/", provider, {"status": "on_the_way"}, expect=200)
    wrong = call("PATCH", f"/api/providers/jobs/{job['id']}/status/", provider, {"status": "working", "arrival_code": "xxxx"})
    assert "arrival_code" in wrong, wrong
    call("PATCH", f"/api/providers/jobs/{job['id']}/status/", provider, {"status": "working", "arrival_code": booking["arrival_code"]}, expect=200)
    step("arrival code checked against the order service")

    call("PATCH", f"/api/providers/jobs/{job['id']}/status/", provider, {"status": "completed"}, expect=200)
    wait_for(lambda: call("GET", f"/api/orders/{order['id']}/", customer)["bookings"][0]["status"] == "completed", "booking completed")
    for s in ("confirmed", "on_the_way", "delivered"):
        call("PATCH", f"/api/admin/orders/{order['id']}/status/", admin, {"status": s})
    final = call("GET", f"/api/orders/{order['id']}/", customer)
    assert final["status"] == "completed" and final["payment_status"] == "paid", final
    step("job completed, products delivered, order completed and COD marked paid")

    earnings = call("GET", "/api/providers/earnings/", provider, expect=200)["summary"]
    step(f"provider earnings pending ৳{earnings['pending']}")

    def stock():
        return call("GET", "/api/products/led-bulb-12w/")["stock"]
    print(f"  · led bulb stock now {stock()}")

    req = call("POST", "/api/custom-requests/", customer, {
        "service_type": "Wall painting", "description": "2 rooms", "area_id": area["id"], "area_name": area["name_en"],
        "address_line": "Road 1", "preferred_date": date.today().isoformat(),
    }, expect=201)
    call("PATCH", f"/api/admin/custom-requests/{req['id']}/quote/", admin,
         {"labor": "3000", "materials": "1000", "platform_fee": "500", "category_slug": "electrical"}, expect=200)
    call("POST", f"/api/custom-requests/{req['id']}/accept/", customer, expect=200)
    wait_for(
        lambda: any(j["source"] == "custom_request" for j in call("GET", "/api/admin/jobs/?source=custom_request", admin)["results"]),
        "custom request job",
    )
    step("custom request quoted, accepted and turned into a provider job")
    print("Phase 1 end-to-end: OK")


if __name__ == "__main__":
    main()
