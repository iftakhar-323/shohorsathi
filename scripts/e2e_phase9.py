"""End-to-end check of Dhap 9 (growth, data, city partnership) through the gateway:
- public transparency dashboard and the authority's CSV feed link (list + mark resolved)
- admin CSV export of issues
- demand forecast, churn list + win-back note, fraud signals
- sponsored listing: listed first, fee shows up in platform revenue
Usage: python3 scripts/e2e_phase9.py [http://localhost:8088]  (stack running, catalog seeded)
"""
import json
import subprocess
import time
import urllib.request

import e2e_phase1 as e1

call, register, wait_for, step, BASE = e1.call, e1.register, e1.wait_for, e1.step, e1.BASE
STAMP = str(int(time.time()))[-8:]


def raw(path, token=None):
    req = urllib.request.Request(BASE + path)
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(req) as res:
        return res.headers.get("Content-Type", ""), res.read().decode("utf-8-sig")


def main():
    admin_phone, cust_phone = f"019{STAMP}", f"017{STAMP}"
    subprocess.run(["docker", "compose", "exec", "-T", "-e", "DJANGO_SUPERUSER_PASSWORD=admin-pass-123", "auth", "python", "manage.py",
                    "createsuperuser", "--noinput", "--phone", admin_phone, "--full_name", "Data Admin"], check=True, capture_output=True)
    admin = call("POST", "/api/auth/login/", body={"phone": admin_phone, "password": "admin-pass-123"}, expect=200)["access"]
    customer = register(cust_phone, "Shathi Akter")["access"]
    area = call("POST", "/api/admin/areas/", admin, {"name_en": f"Ward Area {STAMP}", "name_bn": "ওয়ার্ড এলাকা"}, expect=201)
    step("registered customer and admin")

    # 1. City partnership: report → forward → the ward office's own link resolves it
    issue = call("POST", "/api/issues/", customer, {
        "category": "streetlight", "title": f"Dark lane {STAMP}", "latitude": f"23.7{STAMP[-4:]}", "longitude": "90.40", "area_id": area["id"],
        "area_name": area["name_bn"], "photo_urls": ["/media/public/demo.jpg"], "force": True,
    }, expect=201)
    ward = call("POST", "/api/admin/authorities/", admin, {"name_bn": f"ওয়ার্ড {STAMP}", "name_en": f"Ward {STAMP}", "categories": ["streetlight"]}, expect=201)
    call("POST", f"/api/admin/issues/{issue['id']}/status/", admin, {"status": "forwarded", "authority": ward["id"]}, expect=200)
    feed_token = call("POST", f"/api/admin/authorities/{ward['id']}/rotate-feed/", admin, expect=200)["feed_token"]
    kind, csv_text = raw(f"/api/issues/feed/{feed_token}/")
    assert kind.startswith("text/csv") and f"Dark lane {STAMP}" in csv_text and "Shathi" not in csv_text
    call("POST", f"/api/issues/feed/{feed_token}/{issue['id']}/", body={"status": "resolved", "note": "Bulb replaced"}, expect=200)
    assert call("GET", f"/api/issues/{issue['id']}/", customer, expect=200)["status"] == "resolved"
    report = call("GET", "/api/issues/transparency/?days=30", expect=200)
    assert report["resolved"] >= 1 and any(a["name_en"] == f"Ward {STAMP}" and a["resolved"] == 1 for a in report["by_authority"])
    assert cust_phone not in json.dumps(report)
    _, export = raw("/api/admin/issues/export/", admin)
    assert f"Dark lane {STAMP}" in export
    step("transparency dashboard, authority feed link and CSV export verified")

    # 2. Sponsored listing: the boosted service is listed first and its fee counts as platform income
    services = call("GET", "/api/services/", expect=200)["results"]
    last = services[-1]
    before = call("GET", "/api/admin/analytics/revenue/", admin, expect=200)
    call("POST", f"/api/services/{last['slug']}/sponsor/", admin, {"days": 3, "fee": "750", "sponsor_name": f"Shop {STAMP}"}, expect=201)
    first = call("GET", "/api/services/", expect=200)["results"][0]
    assert first["is_sponsored"] is True
    wait_for(lambda: float(call("GET", "/api/admin/analytics/revenue/", admin, expect=200)["sponsored_listings"])
             >= float(before["sponsored_listings"]) + 750, "sponsored fee in revenue")
    step("sponsored listing ranking and revenue verified")

    # 3. Insights answer (contents depend on how much history the stack has)
    forecast = call("GET", "/api/admin/analytics/forecast/", admin, expect=200)
    assert isinstance(forecast, list) and all(len(c["days"]) == 7 for c in forecast)
    churn = call("GET", "/api/admin/analytics/churn/", admin, expect=200)
    assert isinstance(churn, list)
    me = call("GET", "/api/me/", customer, expect=200)
    call("POST", "/api/admin/analytics/churn/winback/", admin, {"user_ids": [me["id"]], "message": f"Come back {STAMP}"}, expect=200)
    wait_for(lambda: any(n["body_en"] == f"Come back {STAMP}" for n in call("GET", "/api/notifications/", customer, expect=200)["results"]),
             "win-back notification")
    fraud = call("GET", "/api/admin/analytics/fraud/", admin, expect=200)
    assert isinstance(fraud, list)
    call("GET", "/api/admin/analytics/fraud/", customer, expect=403)
    step(f"forecast ({len(forecast)} categories), churn ({len(churn)} at risk), win-back and fraud ({len(fraud)} flags) verified")

    print("\nDhap 9 end-to-end check passed.")


if __name__ == "__main__":
    main()
