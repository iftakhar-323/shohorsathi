"""Fill a fresh stack with realistic demo data for presentations (Bangla names, Dhaka areas, photos).

Run once on an empty stack (see DEMO.md):
    docker compose down -v && docker compose up -d     # wipes all data!
    python3 scripts/seed_demo.py [http://localhost:8088]

Every account uses the password `demo1234`; the admin is created with `createsuperuser`.
The analytics history at the end (8 weeks of bookings and orders) is synthetic, so the
forecast / churn / fraud tabs have something to show; it is marked with user ids 9000+.
"""
import json
import pathlib
import subprocess
import sys
import time
from datetime import date, timedelta

sys.path.insert(0, str(pathlib.Path(__file__).parent))
import e2e_phase1 as e1  # noqa: E402

call, wait_for, step, BASE = e1.call, e1.wait_for, e1.step, e1.BASE
ROOT = pathlib.Path(__file__).resolve().parent.parent
PASSWORD = "demo1234"
IMG = "/media/public/demo"
TODAY = date.today()

ADMIN = ("01700000000", "শহরসাথী অ্যাডমিন")
CUSTOMERS = [("01711000001", "রহিম উদ্দিন"), ("01711000002", "নুসরাত জাহান"), ("01711000003", "তানভীর আহমেদ")]
PROVIDERS = [
    # phone, name, type, skills, gender
    ("01811000001", "করিম মিয়া", "electrician", ["electrical", "appliance"], "male"),
    ("01811000002", "সালমা বেগম", "cleaner", ["cleaning", "pest-control"], "female"),
    ("01811000003", "জামাল হোসেন", "ac_technician", ["ac", "plumbing"], "male"),
]
AREAS = [
    ("Dhaka", "Dhanmondi", "ধানমন্ডি", "23.746466", "90.376015"),
    ("Dhaka", "Mirpur", "মিরপুর", "23.806920", "90.368650"),
    ("Dhaka", "Gulshan", "গুলশান", "23.792496", "90.407806"),
    ("Dhaka", "Uttara", "উত্তরা", "23.875854", "90.379536"),
    ("Dhaka", "Mohammadpur", "মোহাম্মদপুর", "23.765844", "90.358361"),
    ("Dhaka", "Banani", "বনানী", "23.793993", "90.404272"),
    ("Chattogram", "Agrabad", "আগ্রাবাদ", "22.324558", "91.812020"),
    ("Chattogram", "Nasirabad", "নাসিরাবাদ", "22.367090", "91.823410"),
]


def sh(*args, check=True):
    return subprocess.run(args, check=check, capture_output=True, text=True, cwd=ROOT)


def manage(service, *args):
    return sh("docker", "compose", "exec", "-T", service, "python", "manage.py", *args)


def login(phone):
    return call("POST", "/api/auth/login/", body={"phone": phone, "password": PASSWORD}, expect=200)


def register(phone, name):
    """Register with OTP (read from the console SMS log), or log in if the account already exists."""
    res = call("POST", "/api/auth/login/", body={"phone": phone, "password": PASSWORD})
    if res and res.get("access"):
        return res
    return call("POST", "/api/auth/register/", body={"phone": phone, "full_name": name, "password": PASSWORD,
                                                      "otp": e1.otp(phone), "accept_terms": True}, expect=201)


def refreshed(tokens):
    """New access token (picks up a role change); refresh tokens rotate, so keep the new one."""
    tokens.update(call("POST", "/api/auth/token/refresh/", body={"refresh": tokens["refresh"]}, expect=200))
    return tokens["access"]


def role_of(access):
    import base64
    return json.loads(base64.urlsafe_b64decode(access.split(".")[1] + "=="))["role"]


def main():
    # 0. Photos into the media volume, then catalog and subscription plans
    sh("docker", "compose", "exec", "-T", "media", "mkdir", "-p", "/data/media/public")
    sh("docker", "compose", "cp", "demo/images/.", "media:/data/media/public/demo")
    manage("catalog", "seed_catalog")
    manage("subscription", "seed_plans")
    step("photos copied, catalog (8 categories, 14 services, 4 products) and plans seeded")

    # 1. Accounts and areas
    phone, name = ADMIN
    sh("docker", "compose", "exec", "-T", "-e", f"DJANGO_SUPERUSER_PASSWORD={PASSWORD}", "auth", "python", "manage.py",
       "createsuperuser", "--noinput", "--phone", phone, "--full_name", name, check=False)
    admin = login(phone)["access"]
    existing = {(a["city"], a["name_en"]): a for a in call("GET", "/api/areas/", expect=200)}
    areas = {}
    for city, en, bn, lat, lng in AREAS:
        a = existing.get((city, en)) or call("POST", "/api/admin/areas/", admin, {"city": city, "name_en": en, "name_bn": bn}, expect=201)
        areas[en] = {**a, "lat": lat, "lng": lng}
    dhaka_ids = [areas[a[1]]["id"] for a in AREAS if a[0] == "Dhaka"]
    customers = {p: register(p, n) for p, n in CUSTOMERS}
    step(f"admin {ADMIN[0]}, {len(areas)} areas in Dhaka and Chattogram, {len(customers)} customers")

    # 2. Providers: apply, admin approves, online with emergency contact
    providers = {}
    for p_phone, p_name, p_type, skills, gender in PROVIDERS:
        tokens = register(p_phone, p_name)
        if role_of(tokens["access"]) != "provider":
            call("POST", "/api/providers/register/", tokens["access"], {
                "provider_type": p_type, "skills": skills, "area_ids": dhaka_ids, "nid_number": "19901234567890",
                "photo_url": f"{IMG}/services/electrician-visit.jpg", "nid_front_url": f"{IMG}/services/electrician-visit.jpg",
                "payout_method": "bkash", "payout_account": p_phone, "gender": gender, "experience_years": 6,
                "bio": "৬ বছরের অভিজ্ঞতা, সময়মতো ও যত্নের সাথে কাজ করি।",
            })
            pending = call("GET", "/api/admin/providers/?status=pending", admin, expect=200)["results"]
            for p in pending:
                if p["phone"] == p_phone:
                    call("POST", f"/api/admin/providers/{p['id']}/approve/", admin, expect=200)
            wait_for(lambda: role_of(refreshed(tokens)) == "provider", f"{p_name} to become a provider")
        access = refreshed(tokens)
        call("PATCH", "/api/providers/me/", access, {"is_online": True, "emergency_contact_name": "বাবা",
                                                    "emergency_contact_phone": "01700000009"}, expect=200)
        providers[p_phone] = access
    step("3 providers approved and online (electrician, female cleaner, AC technician)")

    # 3. Orders: a finished electrician job with review, a confirmed AC booking, a product order, a pending cleaning job
    rahim, nusrat = customers["01711000001"]["access"], customers["01711000002"]["access"]
    dh = areas["Dhanmondi"]

    def order(token, phone, name, items, area, when=TODAY, slot="11-13", problem=""):
        for old in call("GET", "/api/cart/", token, expect=200)["items"]:  # a half-finished earlier run
            call("DELETE", f"/api/cart/items/{old['id']}/", token)
        details = {}
        for kind, slug, qty in items:
            ci = call("POST", "/api/cart/items/", token, {"item_type": kind, "slug": slug, "quantity": qty}, expect=201)
            if kind == "service":
                details[str(ci["id"])] = {"scheduled_date": when.isoformat(), "slot": slot, "problem_description": problem}
        return call("POST", "/api/orders/", token, {
            "contact_name": name, "contact_phone": phone, "address_line": "বাড়ি ১২, রোড ৭", "area_id": area["id"],
            "area_name": area["name_bn"], "latitude": area["lat"], "longitude": area["lng"], "service_details": details,
        }, expect=201)

    def take(provider, o, finish=True):
        b = o["bookings"][0]
        job = wait_for(lambda: next((j for j in call("GET", "/api/providers/jobs/?tab=available", provider)["results"]
                                     if j["source"] == "booking" and j["source_id"] == b["id"]), None), "job in inbox", timeout=30)
        call("POST", f"/api/providers/jobs/{job['id']}/accept/", provider, expect=200)
        if finish:
            call("PATCH", f"/api/providers/jobs/{job['id']}/status/", provider, {"status": "on_the_way"}, expect=200)
            call("PATCH", f"/api/providers/jobs/{job['id']}/status/", provider,
                 {"status": "working", "arrival_code": b["arrival_code"], "photos": [f"{IMG}/ai-samples/burnt-socket.jpg"]}, expect=200)
            call("PATCH", f"/api/providers/jobs/{job['id']}/status/", provider, {"status": "completed", "note": "সুইচবোর্ড বদলে দেওয়া হয়েছে"}, expect=200)
        return job, b

    o1 = order(rahim, "01711000001", "রহিম উদ্দিন", [("service", "electrician-visit", 1), ("product", "led-bulb-12w", 2)], dh,
               problem="সুইচবোর্ড থেকে পোড়া গন্ধ আসছে")
    _, b1 = take(providers["01811000001"], o1)
    wait_for(lambda: call("GET", f"/api/orders/{o1['id']}/", rahim)["bookings"][0]["status"] == "completed", "booking completed")
    for s in ("confirmed", "on_the_way", "delivered"):
        call("PATCH", f"/api/admin/orders/{o1['id']}/status/", admin, {"status": s})
    call("POST", "/api/providers/reviews/", rahim, {"source": "booking", "source_id": b1["id"], "rating": 5,
                                                    "comment": "খুব দ্রুত এসে সুন্দরভাবে কাজ করেছেন।"})
    o2 = order(rahim, "01711000001", "রহিম উদ্দিন", [("service", "ac-cleaning", 1)], dh, when=TODAY + timedelta(days=2), slot="16-18")
    take(providers["01811000003"], o2, finish=False)
    o3 = order(nusrat, "01711000002", "নুসরাত জাহান", [("service", "home-deep-clean", 1)], areas["Mirpur"],
               when=TODAY + timedelta(days=1), slot="09-11")
    o4 = order(nusrat, "01711000002", "নুসরাত জাহান", [("product", "floor-cleaner-1l", 3), ("product", "extension-board-4", 1)], areas["Mirpur"])
    step(f"orders: {o1['number']} completed + reviewed, {o2['number']} confirmed, {o3['number']} waiting for a cleaner, {o4['number']} products")

    # 4. Subscription, custom request, home profile, AI quote
    sub = call("POST", "/api/subscriptions/", nusrat, {
        "plan": "cleaning-standard", "duration_days": 30, "home_size": 2, "start_date": (TODAY + timedelta(days=1)).isoformat(),
        "preferred_weekday": (TODAY + timedelta(days=1)).weekday(), "slot": "09-11", "area_id": areas["Mirpur"]["id"],
        "area_name": areas["Mirpur"]["name_bn"], "address_line": "বাড়ি ৪, রোড ২", "payment_method": "cod", "prefer_female": True,
    })
    req = call("POST", "/api/custom-requests/", rahim, {
        "service_type": "দুই রুম রং করা", "description": "বসার ঘর ও শোবার ঘর, হালকা রং", "area_id": dh["id"], "area_name": dh["name_bn"],
        "address_line": "বাড়ি ১২, রোড ৭", "preferred_date": (TODAY + timedelta(days=5)).isoformat(),
    }, expect=201)
    call("PATCH", f"/api/admin/custom-requests/{req['id']}/quote/", admin,
         {"labor": "6000", "materials": "4500", "transport": "500", "platform_fee": "600", "category_slug": "painting"})
    call("POST", "/api/home-profiles/", rahim, {
        "name": "ধানমন্ডির বাসা", "address": "বাড়ি ১২, রোড ৭, ধানমন্ডি", "area": dh["id"], "property_type": "apartment",
        "square_feet": 1450, "ac_count": 3, "water_purifier": True, "wiring_age_years": 12, "plumbing_age_years": 6,
        "occupancy_mode": "tenant", "landlord_name": "কবির হোসেন", "landlord_phone": "01799000000",
    }, expect=201)
    call("POST", "/api/custom-requests/ai-quote/", rahim, {"photo_url": f"{IMG}/ai-samples/ac-leak.jpg",
                                                          "description": "এসি থেকে পানি পড়ছে আর ঠান্ডা কম"}, expect=201)
    step(f"subscription {sub.get('status', '?')}, painting request quoted, home profile, AI quote")

    # 5. Provider-side extras: training module, insurance plan
    call("POST", "/api/admin/training-modules/", admin, {
        "slug": "safety-conduct", "title_bn": "নিরাপত্তা ও আচরণবিধি", "title_en": "Safety & conduct",
        "body_bn": "গ্রাহকের বাসায় ঢোকার আগে পরিচয় দিন, জুতা খুলুন, কাজ শেষে জায়গা পরিষ্কার রাখুন। বিপদে SOS চাপুন।",
        "body_en": "Introduce yourself, take off shoes, leave the place clean. Press SOS in danger.",
        "pass_percent": 70, "is_active": True, "questions": [
            {"q": {"bn": "গ্রাহকের বাসায় ঢোকার আগে কী করবেন?", "en": "Before entering a home?"},
             "options": [{"bn": "পরিচয় দেব", "en": "Introduce myself"}, {"bn": "সরাসরি ঢুকব", "en": "Walk in"}], "answer": 0},
            {"q": {"bn": "বিপদে কী করবেন?", "en": "In danger?"},
             "options": [{"bn": "SOS চাপব / ৯৯৯", "en": "Press SOS / 999"}, {"bn": "কিছু না", "en": "Nothing"}], "answer": 0},
        ]})
    call("POST", "/api/admin/insurance-plans/", admin, {
        "name_bn": "দুর্ঘটনা ও স্বাস্থ্য সুরক্ষা", "name_en": "Accident & health cover", "partner": "Green Delta Insurance",
        "weekly_premium": "40.00", "coverage_bn": "দুর্ঘটনায় ৫০,০০০ টাকা পর্যন্ত চিকিৎসা", "coverage_en": "Up to ৳50,000 treatment after accidents",
        "is_active": True})
    call("POST", "/api/providers/training/safety-conduct/submit/", providers["01811000002"], {"answers": [0, 0]})
    step("training module (passed by the cleaner) and insurance plan")

    # 6. City layer: authorities, issues with photos, community posts
    auths = {}
    for key, bn, en, cats in [("ward", "ঢাকা উত্তর সিটি কর্পোরেশন, ওয়ার্ড ৭", "DNCC Ward 7", ["streetlight", "garbage", "road_damage"]),
                              ("wasa", "ঢাকা ওয়াসা, মড্স জোন ৩", "Dhaka WASA, MODS Zone 3", ["waterlogging", "drainage", "water_supply"])]:
        auths[key] = call("POST", "/api/admin/authorities/", admin, {"name_bn": bn, "name_en": en, "categories": cats}, expect=201)
        call("POST", f"/api/admin/authorities/{auths[key]['id']}/rotate-feed/", admin, expect=200)
    issues = [
        ("garbage", "রাস্তার পাশে ময়লার স্তূপ", "তিন দিন ধরে ময়লা নেওয়া হয়নি, গন্ধে হাঁটা যায় না।", "Mirpur", "garbage.jpg", "ward", "in_progress"),
        ("waterlogging", "বৃষ্টির পর হাঁটুপানি", "সাত মসজিদ রোডে প্রতি বৃষ্টিতে পানি জমে থাকে।", "Dhanmondi", "waterlogging.jpg", "wasa", "forwarded"),
        ("streetlight", "গলির বাতি নষ্ট", "রোড ১১-এর গলিতে এক সপ্তাহ ধরে বাতি জ্বলে না।", "Gulshan", "streetlight.jpg", "ward", "resolved"),
        ("road_damage", "রাস্তায় বড় গর্ত", "রিকশা উল্টে যাওয়ার ঝুঁকি।", "Uttara", "road.jpg", None, "reported"),
    ]
    reporters = [rahim, nusrat, customers["01711000003"]["access"]]
    for i, (cat, title, desc, area, photo, auth, status) in enumerate(issues):
        a = areas[area]
        issue = call("POST", "/api/issues/", reporters[i % 3], {
            "category": cat, "title": title, "description": desc, "latitude": a["lat"], "longitude": a["lng"], "area_id": a["id"],
            "area_name": a["name_bn"], "photo_urls": [f"{IMG}/issues/{photo}"], "force": True}, expect=201)
        for other in reporters:
            if other is not reporters[i % 3]:  # the reporter's own vote is already counted; upvote toggles
                call("POST", f"/api/issues/{issue['id']}/upvote/", other)
        if auth:
            call("POST", f"/api/admin/issues/{issue['id']}/status/", admin, {"status": "forwarded", "authority": auths[auth]["id"]}, expect=200)
        if status in ("in_progress", "resolved"):
            call("POST", f"/api/admin/issues/{issue['id']}/status/", admin, {"status": "in_progress", "note": "কাজ শুরু হয়েছে"}, expect=200)
        if status == "resolved":
            call("POST", f"/api/admin/issues/{issue['id']}/status/", admin,
                 {"status": "resolved", "note": "নতুন এলইডি বাতি লাগানো হয়েছে", "photos": [f"{IMG}/products/led-bulb-12w.jpg"]}, expect=200)
    for token, area, kind, body in [
        (rahim, "Dhanmondi", "alert", "আগামীকাল সকাল ১০টা থেকে ২টা পর্যন্ত রোড ৭-এ পানি থাকবে না।"),
        (nusrat, "Mirpur", "recommendation", "সালমা আপা খুব যত্ন করে পুরো বাসা পরিষ্কার করেছেন, সবাইকে সাজেস্ট করছি।"),
        (customers["01711000003"]["access"], "Uttara", "question", "উত্তরায় ভালো এসি টেকনিশিয়ান কে আছেন?"),
    ]:
        call("POST", "/api/community/posts/", token, {"area_id": areas[area]["id"], "area_name": areas[area]["name_bn"], "kind": kind, "body": body}, expect=201)
    step("2 authorities with feed links, 4 photo issues (one resolved), 3 community posts")

    # 7. Offers: seasonal packages with banners, group deal, sponsored listing
    services = {s["slug"]: s for s in call("GET", "/api/services/?page_size=50", expect=200)["results"]}
    for title_bn, title_en, season, tag_bn, tag_en, slugs, pct, banner in [
        ("গ্রীষ্মের এসি চেকআপ", "Summer AC check-up", "summer", "গরম আসার আগেই এসি তৈরি রাখুন", "Get your AC ready before the heat", ["ac-cleaning", "ac-gas-refill"], 15, "summer-ac.jpg"),
        ("বর্ষায় মশা ও পানি সুরক্ষা", "Monsoon protection", "monsoon", "ডেঙ্গু থেকে বাঁচতে ফগিং আর লিক মেরামত", "Fogging against dengue, leak repair", ["mosquito-fogging", "plumber-visit"], 10, "monsoon.jpg"),
        ("ঈদের আগে ঝকঝকে বাসা", "Eid home makeover", "eid", "ডিপ ক্লিন আর সোফা ক্লিনিংয়ে ২০% ছাড়", "20% off deep clean and sofa cleaning", ["home-deep-clean", "sofa-carpet-cleaning"], 20, "eid-cleaning.jpg"),
    ]:
        call("POST", "/api/seasonal-packages/", admin, {
            "title_bn": title_bn, "title_en": title_en, "season": season, "tagline_bn": tag_bn, "tagline_en": tag_en, "service_slugs": slugs,
            "discount_percent": pct, "banner_image_url": f"{IMG}/banners/{banner}",
            "active_from": (TODAY - timedelta(days=3)).isoformat(), "active_until": (TODAY + timedelta(days=40)).isoformat()}, expect=201)
    deal = call("POST", "/api/group-deals/", admin, {
        "title_bn": "ধানমন্ডি রোড ৭: এসি ক্লিনিং গ্রুপ ডিল", "title_en": "Dhanmondi Road 7: AC cleaning group deal",
        "service": services["ac-cleaning"]["id"], "target_participants": 4, "discount_percent": 25, "area_ids": [dh["id"]],
        "expires_at": f"{(TODAY + timedelta(days=10)).isoformat()}T18:00:00+06:00"}, expect=201)
    for token in (rahim, nusrat):
        call("POST", f"/api/group-deals/{deal['id']}/join/", token, expect=200)
    call("POST", "/api/services/wall-painting/sponsor/", admin, {"days": 14, "fee": "2500", "sponsor_name": "Berger Paints Dealer, Dhanmondi"}, expect=201)
    step("3 seasonal packages, a group deal (2/4 joined), a sponsored listing")

    # 8. Synthetic analytics history for the insight tabs
    sh("docker", "compose", "cp", "scripts/demo_analytics_history.py", "analytics:/tmp/demo_history.py")
    out = sh("docker", "compose", "exec", "-T", "analytics", "python", "manage.py", "shell", "-c", "exec(open('/tmp/demo_history.py').read())")
    step(out.stdout.strip().splitlines()[-1] if out.stdout.strip() else "analytics history added")

    print(f"""
Demo data ready. Password for every account: {PASSWORD}
  admin     {ADMIN[0]}   → admin panel
  customer  01711000001 (রহিম, tenant in Dhanmondi) / 01711000002 (নুসরাত, Mirpur)
  provider  01811000001 (electrician) / 01811000002 (female cleaner) / 01811000003 (AC technician)
""")


if __name__ == "__main__":
    t = time.time()
    main()
    print(f"done in {time.time() - t:.0f}s")
