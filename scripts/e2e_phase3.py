"""End-to-end smoke test of Phase 3 (city issues, community, emergency request, live tracking).
Usage: python3 scripts/e2e_phase3.py [http://localhost:8088]  (stack running, catalog seeded)"""
import subprocess
import time
from datetime import date

import e2e_phase1 as e1

call, register, wait_for, step = e1.call, e1.register, e1.wait_for, e1.step
STAMP = str(int(time.time()))[-8:]


def main():
    admin_phone, a_phone, b_phone, pro_phone = f"019{STAMP}", f"017{STAMP}", f"015{STAMP}", f"013{STAMP}"
    subprocess.run(["docker", "compose", "exec", "-T", "-e", "DJANGO_SUPERUSER_PASSWORD=admin-pass-123", "auth", "python", "manage.py",
                    "createsuperuser", "--noinput", "--phone", admin_phone, "--full_name", "E2E Admin"], check=True, capture_output=True)
    admin = call("POST", "/api/auth/login/", body={"phone": admin_phone, "password": "admin-pass-123"}, expect=200)["access"]
    area = call("POST", "/api/admin/areas/", admin, {"name_en": f"Area {STAMP}", "name_bn": "এলাকা"}, expect=201)
    alice = register(a_phone, "Alice")["access"]
    bob = register(b_phone, "Bob")["access"]

    spot = {"category": "streetlight", "title": "Dark lane", "latitude": "23.780001", "longitude": "90.400001", "area_id": area["id"],
            "area_name": area["name_en"], "photo_urls": ["/media/public/x.jpg"]}
    issue = call("POST", "/api/issues/", alice, spot, expect=201)
    dup = call("POST", "/api/issues/", bob, {**spot, "latitude": "23.780100"})
    assert dup["duplicate"]["id"] == issue["id"], dup
    assert call("POST", f"/api/issues/{issue['id']}/upvote/", bob, expect=200)["upvote_count"] == 2
    step("issue reported; nearby duplicate detected; neighbour upvoted instead")

    office = call("POST", "/api/admin/authorities/", admin, {"name_bn": "ওয়ার্ড অফিস", "name_en": "Ward office", "categories": ["streetlight"]}, expect=201)
    call("POST", f"/api/admin/issues/{issue['id']}/status/", admin, {"status": "forwarded", "authority": office["id"]}, expect=200)
    call("POST", f"/api/admin/issues/{issue['id']}/status/", admin, {"status": "resolved", "photos": ["/media/public/fixed.jpg"]}, expect=200)
    wait_for(lambda: any(n["kind"] == "issue.status_changed" for n in call("GET", "/api/notifications/", bob)["results"]), "upvoter notified")
    step("admin forwarded to the ward office and resolved it; reporter and upvoter notified")

    post = call("POST", "/api/community/posts/", alice, {"area_id": area["id"], "area_name": area["name_en"], "kind": "tip", "body": "Water off tomorrow 10–2"}, expect=201)
    call("POST", f"/api/community/posts/{post['id']}/like/", bob, expect=200)
    call("POST", f"/api/community/posts/{post['id']}/comments/", bob, {"body": "Thanks!"}, expect=201)
    feed = call("GET", f"/api/community/posts/?area={area['id']}")["results"][0]
    assert feed["like_count"] == 1 and feed["comment_count"] == 1
    step("community tip posted, liked and commented")

    pro_tokens = register(pro_phone, "Fast Electrician")
    call("POST", "/api/providers/register/", pro_tokens["access"], {
        "provider_type": "electrician", "skills": ["electrical"], "area_ids": [area["id"]], "nid_number": "1234567890",
        "photo_url": "/media/x.jpg", "nid_front_url": "/api/media/1/download/"}, expect=201)
    pid = [p for p in call("GET", "/api/admin/providers/?status=pending", admin)["results"] if p["phone"] == pro_phone][0]["id"]
    call("POST", f"/api/admin/providers/{pid}/approve/", admin, expect=200)
    pro = pro_tokens["access"]
    call("PATCH", "/api/providers/me/", pro, {"is_online": True}, expect=200)
    call("POST", "/api/providers/me/location/", pro, {"latitude": "23.781", "longitude": "90.401"})

    item = call("POST", "/api/cart/items/", alice, {"item_type": "service", "slug": "electrician-visit"}, expect=201)
    order = call("POST", "/api/orders/", alice, {
        "contact_name": "Alice", "contact_phone": a_phone, "address_line": "Road 1", "area_id": area["id"], "area_name": area["name_en"],
        "latitude": "23.780", "longitude": "90.400",
        "service_details": {str(item["id"]): {"scheduled_date": date.today().isoformat(), "slot": "20-22", "is_emergency": True}},
    }, expect=201)
    booking = order["bookings"][0]
    assert booking["is_emergency"] and float(booking["surcharge"]) > 0
    wait_for(lambda: any(n["kind"] == "emergency.raised" for n in call("GET", "/api/notifications/", pro)["results"]), "emergency alert to online provider")
    step(f"emergency booking with ৳{booking['surcharge']} priority charge; nearest online provider alerted")

    job = wait_for(lambda: next((j for j in call("GET", "/api/providers/jobs/?tab=available", pro)["results"] if j["is_emergency"]), None), "emergency job")
    call("POST", f"/api/providers/jobs/{job['id']}/accept/", pro, expect=200)
    call("PATCH", f"/api/providers/jobs/{job['id']}/status/", pro, {"status": "on_the_way"}, expect=200)
    call("POST", "/api/providers/me/location/", pro, {"latitude": "23.7805", "longitude": "90.4005"})
    track = call("GET", f"/api/providers/tracking/booking/{booking['id']}/", alice, expect=200)
    assert track["available"] and track["latitude"] == "23.780500", track
    step("provider on the way; customer sees live location")
    print("Phase 3 end-to-end: OK")


if __name__ == "__main__":
    main()
