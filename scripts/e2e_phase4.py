"""End-to-end smoke test of Phase 4 (wallet & points, referrals, B2B portal, analytics, multi-city).
Usage: python3 scripts/e2e_phase4.py [http://localhost:8088]  (stack running, catalog seeded)"""
import subprocess
import time
from datetime import date, timedelta

import e2e_phase1 as e1
from e2e_phase2 import form_post

call, register, wait_for, step = e1.call, e1.register, e1.wait_for, e1.step
STAMP = str(int(time.time()))[-8:]


def run_in(service, code):
    subprocess.run(["docker", "compose", "exec", "-T", service, "python", "-c",
                    "import django,os;os.environ.setdefault('DJANGO_SETTINGS_MODULE','config.settings');django.setup();" + code],
                   check=True, capture_output=True)


def main():
    admin_phone, ref_phone, cust_phone, pro_phone = f"019{STAMP}", f"014{STAMP}", f"017{STAMP}", f"013{STAMP}"
    subprocess.run(["docker", "compose", "exec", "-T", "-e", "DJANGO_SUPERUSER_PASSWORD=admin-pass-123", "auth", "python", "manage.py",
                    "createsuperuser", "--noinput", "--phone", admin_phone, "--full_name", "E2E Admin"], check=True, capture_output=True)
    admin = call("POST", "/api/auth/login/", body={"phone": admin_phone, "password": "admin-pass-123"}, expect=200)["access"]
    city = "Sylhet"
    area = call("POST", "/api/admin/areas/", admin, {"city": city, "name_en": f"Zindabazar {STAMP}", "name_bn": "জিন্দাবাজার"}, expect=201)
    assert city in call("GET", "/api/cities/")
    step(f"city '{city}' is live just by having areas")

    referrer = register(ref_phone, "Referrer")["access"]
    code = call("GET", "/api/loyalty/me/", referrer, expect=200)["referral_code"]
    customer = register(cust_phone, "Wallet User")["access"]
    call("POST", "/api/loyalty/referral/", customer, {"code": code}, expect=200)

    topup = call("POST", "/api/loyalty/topups/", customer, {"amount": "1000"}, expect=201)
    start = call("POST", "/api/payments/initiate/", customer, {"purpose": "wallet_topup", "reference_id": topup["id"]}, expect=201)
    loc = form_post("/api/payments/gateway/success/", {"tran_id": start["tran_id"], "amount": start["amount"], "val_id": f"mock-{start['tran_id']}"})
    assert "status=released" in loc, loc
    wait_for(lambda: call("GET", "/api/loyalty/me/", customer)["wallet"] == "1000.00", "wallet top-up credited")
    step("wallet topped up ৳1000 via mock bKash; referral code applied")

    pro_tokens = register(pro_phone, "Pro")
    call("POST", "/api/providers/register/", pro_tokens["access"], {
        "provider_type": "electrician", "skills": ["electrical", "pest-control"], "area_ids": [area["id"]], "nid_number": "1234567890",
        "photo_url": "/media/x.jpg", "nid_front_url": "/api/media/1/download/"}, expect=201)
    pid = [p for p in call("GET", "/api/admin/providers/?status=pending", admin)["results"] if p["phone"] == pro_phone][0]["id"]
    call("POST", f"/api/admin/providers/{pid}/approve/", admin, expect=200)
    pro = pro_tokens["access"]

    def order(token, **extra):
        item = call("POST", "/api/cart/items/", token, {"item_type": "service", "slug": "electrician-visit"}, expect=201)
        return call("POST", "/api/orders/", token, {
            "contact_name": "Wallet User", "contact_phone": cust_phone, "address_line": "Road 1", "area_id": area["id"], "area_name": area["name_en"],
            "service_details": {str(item["id"]): {"scheduled_date": (date.today() + timedelta(days=1)).isoformat(), "slot": "09-11"}}, **extra}, expect=201)

    def complete(order_id):
        job = wait_for(lambda: next((j for j in call("GET", "/api/providers/jobs/?tab=available", pro)["results"] if j["source"] == "booking"), None), "job")
        call("POST", f"/api/providers/jobs/{job['id']}/accept/", pro, expect=200)
        for s in ("on_the_way", "working", "completed"):
            body = {"status": s}
            if s == "working":
                code_ = call("GET", f"/api/orders/{order_id}/", customer)["bookings"][0]["arrival_code"]
                body["arrival_code"] = code_
            call("PATCH", f"/api/providers/jobs/{job['id']}/status/", pro, body, expect=200)
        wait_for(lambda: call("GET", f"/api/orders/{order_id}/", customer)["status"] == "completed", "order completed")

    o1 = order(customer, payment_method="wallet")
    assert o1["payment_status"] == "paid"
    complete(o1["id"])
    acc = wait_for(lambda: (lambda a: a if a["points"] > 0 else None)(call("GET", "/api/loyalty/me/", customer)), "points earned")
    ref_acc = wait_for(lambda: (lambda a: a if a["wallet"] == "100.00" else None)(call("GET", "/api/loyalty/me/", referrer)), "referral bonus")
    step(f"paid ৳{o1['total']} from wallet; completed; earned {acc['points']} points; referrer got ৳{ref_acc['wallet']} and new user a welcome bonus")

    o2 = order(customer, redeem_points=acc["points"])
    assert float(o2["discount"]) > 0
    call("POST", f"/api/orders/{o2['id']}/cancel/", customer, expect=200)
    wait_for(lambda: call("GET", "/api/loyalty/me/", customer)["points"] == acc["points"], "points returned on cancel")
    step(f"points redeemed for ৳{o2['discount']} off; returned when the order was cancelled")

    org = call("POST", "/api/b2b/orgs/", customer, {"name": f"Green View {STAMP}", "kind": "building", "contact_name": "Secretary",
                                                   "contact_phone": cust_phone, "address_line": "Road 7", "area_id": area["id"], "area_name": area["name_en"], "units": 24}, expect=201)
    call("POST", f"/api/admin/b2b/orgs/{org['id']}/approve/", admin, expect=200)
    call("POST", f"/api/b2b/orgs/{org['id']}/members/", customer, {"phone": ref_phone}, expect=201)
    tomorrow = date.today() + timedelta(days=1)
    call("POST", f"/api/admin/b2b/orgs/{org['id']}/contracts/", admin, {
        "title": "Monthly pest control", "category_slug": "pest-control", "visits_per_month": 1, "preferred_weekday": tomorrow.weekday(),
        "monthly_fee": "3000", "start_date": tomorrow.isoformat(), "end_date": (tomorrow + timedelta(days=90)).isoformat()}, expect=201)
    run_in("b2b-worker", "from b2b_app import logic; logic.dispatch_tomorrow()")
    wait_for(lambda: any(j["source"] == "b2b_visit" for j in call("GET", "/api/providers/jobs/?tab=available", pro)["results"]), "contract visit job")
    o3 = order(customer, organization_id=org["id"])
    assert o3["organization_id"] == org["id"]
    inv = call("POST", f"/api/admin/b2b/orgs/{org['id']}/invoice/", admin, {"period": date.today().strftime("%Y-%m")}, expect=201)
    html = urllib_get(f"/api/b2b/invoices/{inv['id']}/print/", customer)
    assert "Green View" in html
    step(f"organization approved, member added, contract visit dispatched, invoice {inv['number']} ৳{inv['total']} printable")

    summary = wait_for(lambda: (lambda s: s if s["orders"] >= 3 else None)(call("GET", f"/api/admin/analytics/summary/?city={city}", admin)), "analytics facts")
    step(f"analytics for {city}: {summary['orders']} orders, GMV ৳{summary['gmv']}, commission ৳{summary['commission']}")
    print("Phase 4 end-to-end: OK")


def urllib_get(path, token):
    import urllib.request

    req = urllib.request.Request(e1.BASE + path, headers={"Authorization": f"Bearer {token}"})
    return urllib.request.urlopen(req).read().decode()


if __name__ == "__main__":
    main()
