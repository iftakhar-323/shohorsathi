"""End-to-end smoke test of Phase 2 (subscriptions, online payment + escrow, reviews, chat, notifications).

Needs the stack running, seeded catalog (`seed_catalog`) and plans (`docker compose exec subscription python manage.py seed_plans`).
Usage: python3 scripts/e2e_phase2.py [http://localhost:8088]
"""
import re
import subprocess
import sys
import time
import urllib.parse
import urllib.request
from datetime import date, timedelta

import e2e_phase1 as e1

BASE = e1.BASE
STAMP = str(int(time.time()))[-8:]
call, register, wait_for, step = e1.call, e1.register, e1.wait_for, e1.step


def form_post(path, fields):
    """Browser-style form POST that does not follow the redirect; returns the Location header."""
    req = urllib.request.Request(BASE + path, data=urllib.parse.urlencode(fields).encode(), method="POST")

    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *a, **k):
            return None

    try:
        urllib.request.build_opener(NoRedirect).open(req)
    except urllib.error.HTTPError as e:
        return e.headers.get("Location", "")
    return ""


def pay_with_mock(token, purpose, reference_id):
    start = call("POST", "/api/payments/initiate/", token, {"purpose": purpose, "reference_id": reference_id}, expect=201)
    page = urllib.request.urlopen(start["redirect_url"].replace("http://localhost:8088", BASE)).read().decode()
    assert start["tran_id"] in page
    location = form_post("/api/payments/gateway/success/", {"tran_id": start["tran_id"], "amount": start["amount"], "val_id": f"mock-{start['tran_id']}", "card_type": "bKash"})
    assert "status=held" in location, location
    return start


def manage(service, *args):
    subprocess.run(["docker", "compose", "exec", "-T", service, "python", "manage.py", *args], check=True, capture_output=True)


def main():
    admin_phone, customer_phone, cleaner_phone = f"019{STAMP}", f"017{STAMP}", f"016{STAMP}"
    subprocess.run(["docker", "compose", "exec", "-T", "-e", "DJANGO_SUPERUSER_PASSWORD=admin-pass-123", "auth", "python", "manage.py",
                    "createsuperuser", "--noinput", "--phone", admin_phone, "--full_name", "E2E Admin"], check=True, capture_output=True)
    admin = call("POST", "/api/auth/login/", body={"phone": admin_phone, "password": "admin-pass-123"}, expect=200)["access"]
    area = call("POST", "/api/admin/areas/", admin, {"name_en": f"Area {STAMP}", "name_bn": "এলাকা"}, expect=201)
    manage("subscription", "seed_plans")

    cleaner_tokens = register(cleaner_phone, "E2E Cleaner")
    call("POST", "/api/providers/register/", cleaner_tokens["access"], {
        "provider_type": "cleaner", "skills": ["cleaning", "electrical"], "area_ids": [area["id"]], "nid_number": "1234567890",
        "photo_url": "/media/x.jpg", "nid_front_url": "/api/media/1/download/", "payout_method": "bkash", "payout_account": cleaner_phone,
    }, expect=201)
    pid = [p for p in call("GET", "/api/admin/providers/?status=pending", admin)["results"] if p["phone"] == cleaner_phone][0]["id"]
    call("POST", f"/api/admin/providers/{pid}/approve/", admin, expect=200)
    cleaner = cleaner_tokens["access"]
    step("cleaner approved")

    customer = register(customer_phone, "E2E Subscriber")["access"]
    start_day = date.today() + timedelta(days=1)
    sub = call("POST", "/api/subscriptions/", customer, {
        "plan": "cleaning-standard", "duration_days": 30, "home_size": 2, "start_date": start_day.isoformat(),
        "preferred_weekday": start_day.weekday(), "slot": "09-11", "area_id": area["id"], "area_name": area["name_en"],
        "address_line": "Road 1", "payment_method": "online",
    }, expect=201)
    assert sub["status"] == "pending_payment"
    step(f"subscription created (৳{sub['amount_due']}), waiting for payment")

    pay_with_mock(customer, "subscription", sub["id"])
    wait_for(lambda: call("GET", f"/api/subscriptions/{sub['id']}/", customer)["status"] == "active", "payment.succeeded to activate the subscription")
    balances = call("GET", "/api/admin/payments/balances/", admin)
    step(f"paid via mock bKash; subscription active; escrow now ৳{balances['escrow']}")

    wait_for(lambda: call("GET", "/api/notifications/unread-count/", customer)["unread"] >= 2, "notifications")
    titles = [n["title_en"] for n in call("GET", "/api/notifications/", customer)["results"]]
    step(f"customer notifications: {titles[:3]}")

    subprocess.run(["docker", "compose", "exec", "-T", "subscription", "python", "-c",
                    "import django,os;os.environ.setdefault('DJANGO_SETTINGS_MODULE','config.settings');django.setup();"
                    "from subscriptions import logic;print(logic.dispatch_tomorrow())"], check=True, capture_output=True)
    job = wait_for(lambda: next(iter(call("GET", "/api/providers/jobs/?tab=available", cleaner)["results"]), None), "visit job in the cleaner's inbox")
    assert job["source"] == "subscription_visit"
    for s in ("accept", None):
        if s:
            call("POST", f"/api/providers/jobs/{job['id']}/accept/", cleaner, expect=200)
    for s in ("on_the_way", "working", "completed"):
        call("PATCH", f"/api/providers/jobs/{job['id']}/status/", cleaner, {"status": s}, expect=200)
    visit_id = job["source_id"]
    wait_for(lambda: call("GET", f"/api/subscriptions/{sub['id']}/", customer)["preferred_provider_name"] == "E2E Cleaner", "same-cleaner pin")
    step("visit dispatched, done by the cleaner, who is now pinned to this home")

    call("POST", f"/api/subscriptions/visits/{visit_id}/rate/", customer, {"rating": 5, "feedback": "Spotless"}, expect=200)
    wait_for(lambda: call("GET", "/api/providers/me/", cleaner)["rating_count"] == 1, "rating to reach the provider")
    step("visit rated; provider rating updated")

    conv = call("POST", "/api/chat/conversations/", customer, {"kind": "job", "source": "subscription_visit", "source_id": visit_id}, expect=201)
    call("POST", f"/api/chat/conversations/{conv['id']}/messages/", customer, {"body": "পরের বার বারান্দাও করবেন?"}, expect=201)
    wait_for(lambda: call("GET", "/api/chat/unread/", cleaner)["unread"] == 1, "chat unread for provider")
    support = call("POST", "/api/chat/conversations/", customer, {"kind": "support", "subject": "Payment", "body": "bKash payment question"}, expect=201)
    bot = call("GET", f"/api/chat/conversations/{support['id']}/messages/", customer)["messages"][-1]
    assert bot["sender_role"] == "bot"
    step("job chat and support chat (FAQ bot replied)")

    item = call("POST", "/api/cart/items/", customer, {"item_type": "service", "slug": "electrician-visit"}, expect=201)
    order = call("POST", "/api/orders/", customer, {
        "contact_name": "E2E Subscriber", "contact_phone": customer_phone, "address_line": "Road 1", "area_id": area["id"],
        "area_name": area["name_en"], "payment_method": "online",
        "service_details": {str(item["id"]): {"scheduled_date": start_day.isoformat(), "slot": "14-16"}},
    }, expect=201)
    pay_with_mock(customer, "order", order["id"])
    wait_for(lambda: call("GET", f"/api/orders/{order['id']}/", customer)["payment_status"] == "paid", "order paid")
    wait_for(lambda: any(j["source"] == "booking" for j in call("GET", "/api/providers/jobs/?tab=available", cleaner)["results"]), "paid order booking dispatched")
    call("POST", f"/api/orders/{order['id']}/cancel/", customer, expect=200)
    wait_for(lambda: call("GET", f"/api/orders/{order['id']}/", customer)["payment_status"] == "refunded", "automatic refund")
    step("online order paid, dispatched after payment, cancelled and refunded automatically")
    print("Phase 2 end-to-end: OK")


if __name__ == "__main__":
    main()
