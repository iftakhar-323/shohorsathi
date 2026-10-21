"""End-to-end check of Dhap 5 (data protection): consent, encrypted NID, data export, account deletion across services.
Usage: python3 scripts/e2e_phase5.py [http://localhost:8088]  (stack running, catalog seeded)"""
import json
import subprocess
import time
import urllib.request
import uuid
from datetime import date, timedelta

import e2e_phase1 as e1

call, register, wait_for, step = e1.call, e1.register, e1.wait_for, e1.step
STAMP = str(int(time.time()))[-8:]
PNG = b"\x89PNG\r\n\x1a\n" + b"e2e-nid-image-bytes" * 20


def upload(token, purpose):
    boundary = uuid.uuid4().hex
    body = (f"--{boundary}\r\nContent-Disposition: form-data; name=\"purpose\"\r\n\r\n{purpose}\r\n"
            f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"nid.png\"\r\nContent-Type: image/png\r\n\r\n").encode() + PNG + f"\r\n--{boundary}--\r\n".encode()
    req = urllib.request.Request(e1.BASE + "/api/media/", data=body, method="POST")
    req.add_header("Content-Type", f"multipart/form-data; boundary={boundary}")
    req.add_header("Authorization", f"Bearer {token}")
    return json.loads(urllib.request.urlopen(req).read())


def raw_get(path, token):
    req = urllib.request.Request(e1.BASE + path, headers={"Authorization": f"Bearer {token}"})
    try:
        with urllib.request.urlopen(req) as res:
            return res.status, res.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()


def sql(db, query):
    return subprocess.run(["docker", "compose", "exec", "-T", "postgres", "psql", "-U", "shohor", "-d", db, "-Atc", query],
                          capture_output=True, text=True, check=True).stdout.strip()


def main():
    admin_phone, phone = f"019{STAMP}", f"016{STAMP}"
    subprocess.run(["docker", "compose", "exec", "-T", "-e", "DJANGO_SUPERUSER_PASSWORD=admin-pass-123", "auth", "python", "manage.py",
                    "createsuperuser", "--noinput", "--phone", admin_phone, "--full_name", "E2E Admin"], check=True, capture_output=True)
    admin = call("POST", "/api/auth/login/", body={"phone": admin_phone, "password": "admin-pass-123"}, expect=200)["access"]
    area = call("POST", "/api/admin/areas/", admin, {"name_en": f"Privacy {STAMP}", "name_bn": "এলাকা"}, expect=201)

    tokens = register(phone, "Privacy Tester")
    token = tokens["access"]
    me = call("GET", "/api/me/", token, expect=200)
    assert me["terms_version"] and me["terms_accepted_at"]
    step(f"consent recorded at sign-up (terms {me['terms_version']})")

    nid = upload(token, "nid")
    media_id = nid["id"]
    stored = sql("media_db", f"SELECT file FROM files_mediafile WHERE id={media_id}")
    on_disk = subprocess.run(["docker", "compose", "exec", "-T", "media", "cat", f"/data/media/{stored}"], capture_output=True, check=True).stdout
    assert PNG not in on_disk, "NID must be encrypted at rest"
    status, body = raw_get(nid["url"], admin)
    assert status == 200 and body == PNG
    assert call("GET", f"/api/admin/media/{media_id}/access-log/", admin, expect=200)[0]["role"] == "admin"
    step("NID stored encrypted, decrypted for the admin, and the viewing logged")

    call("POST", "/api/providers/register/", token, {"provider_type": "electrician", "skills": ["electrical"], "area_ids": [area["id"]],
                                                    "nid_number": "1234567890", "photo_url": "/media/x.jpg", "nid_front_url": nid["url"]}, expect=201)
    item = call("POST", "/api/cart/items/", token, {"item_type": "service", "slug": "electrician-visit"}, expect=201)
    order = call("POST", "/api/orders/", token, {"contact_name": "Privacy Tester", "contact_phone": phone, "address_line": "Secret Road 9",
                                                 "area_id": area["id"], "area_name": area["name_en"],
                                                 "service_details": {str(item["id"]): {"scheduled_date": (date.today() + timedelta(days=1)).isoformat(), "slot": "09-11"}}}, expect=201)
    export = call("GET", "/api/me/export/", token, expect=200)
    assert export["profile"]["phone"] == phone and export["order"][0]["address"].startswith("Secret Road 9")
    assert export["provider"]["provider_profile"]["nid_number"] == "1234567890"
    step("data export gathers profile, orders and provider profile from their services")

    assert call("POST", "/api/me/delete/", token, {"password": "wrong-password"})["_status"] == 400
    call("POST", "/api/me/delete/", token, {"password": "strong-pass-123"}, expect=204)
    wait_for(lambda: sql("order_db", f"SELECT address_line FROM orders_order WHERE id={order['id']}") == "", "order redacted")
    wait_for(lambda: sql("provider_db", f"SELECT status FROM providers_provider WHERE phone='' AND full_name='Deleted user' AND nid_number=''") != "", "provider purged")
    wait_for(lambda: sql("media_db", f"SELECT count(*) FROM files_mediafile WHERE id={media_id}") == "0", "NID file deleted")
    assert call("POST", "/api/auth/login/", body={"phone": phone, "password": "strong-pass-123"})["_status"] == 401
    assert call("GET", "/api/me/", token)["_status"] == 401
    step("account deleted: login blocked, order address redacted, provider documents and NID file removed")

    unsent = sql("order_db", "SELECT count(*) FROM shohor_common_outboxevent WHERE sent_at IS NULL")
    assert unsent == "0", f"{unsent} events stuck in the order outbox"
    step("every published event left the outbox")
    print("Dhap 5 end-to-end: OK")


if __name__ == "__main__":
    main()
