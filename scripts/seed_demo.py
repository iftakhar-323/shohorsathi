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
CUSTOMERS = [("01711000001", "রহিম উদ্দিন"), ("01711000002", "নুসরাত জাহান"), ("01711000003", "তানভীর আহমেদ"),
             # Khulna
             ("01711000004", "ফারহানা ইসলাম"), ("01711000005", "আরিফ হাসান"), ("01711000006", "সুমাইয়া আক্তার"),
             ("01711000007", "রাকিব হাসান"), ("01711000008", "তাসলিমা খাতুন")]
PROVIDERS = [
    # phone, name, type, skills, gender
    ("01811000001", "করিম মিয়া", "electrician", ["electrical", "appliance"], "male"),
    ("01811000002", "সালমা বেগম", "cleaner", ["cleaning", "pest-control"], "female"),
    ("01811000003", "জামাল হোসেন", "ac_technician", ["ac", "plumbing"], "male"),
    # Khulna
    ("01811000004", "মাসুদ রানা", "electrician", ["electrical", "appliance"], "male"),
    ("01811000005", "রেহানা খাতুন", "cleaner", ["cleaning", "pest-control"], "female"),
    ("01811000006", "সাইফুল ইসলাম", "ac_technician", ["ac", "plumbing"], "male"),
    ("01811000007", "নাজমুল হক", "painter", ["painting", "moving"], "male"),
]
HOME_ADDRESSES = {
    "01711000001": ("Dhanmondi", "বাড়ি ১২, রোড ৭"), "01711000002": ("Mirpur", "বাড়ি ৪, রোড ২"),
    "01711000003": ("Uttara", "বাড়ি ৭, সেক্টর ৪"), "01711000004": ("Sonadanga", "বাড়ি ৩৪, মজিদ সরণি"),
    "01711000005": ("Khalishpur", "হাউজিং এস্টেট, ব্লক বি"), "01711000006": ("Boyra", "বয়রা মেইন রোড, বাড়ি ৯"),
    "01711000007": ("Nirala", "নিরালা আবাসিক, রোড ১৩"), "01711000008": ("Dakbangla", "কে ডি ঘোষ রোড, বাড়ি ২১"),
}
KHULNA_PROVIDERS = {"01811000004", "01811000005", "01811000006", "01811000007"}
AREAS = [
    ("Dhaka", "Dhanmondi", "ধানমন্ডি", "23.746466", "90.376015"),
    ("Dhaka", "Mirpur", "মিরপুর", "23.806920", "90.368650"),
    ("Dhaka", "Gulshan", "গুলশান", "23.792496", "90.407806"),
    ("Dhaka", "Uttara", "উত্তরা", "23.875854", "90.379536"),
    ("Dhaka", "Mohammadpur", "মোহাম্মদপুর", "23.765844", "90.358361"),
    ("Dhaka", "Banani", "বনানী", "23.793993", "90.404272"),
    ("Chattogram", "Agrabad", "আগ্রাবাদ", "22.324558", "91.812020"),
    ("Chattogram", "Nasirabad", "নাসিরাবাদ", "22.367090", "91.823410"),
    ("Khulna", "Sonadanga", "সোনাডাঙ্গা", "22.815500", "89.548000"),
    ("Khulna", "Khalishpur", "খালিশপুর", "22.858000", "89.534000"),
    ("Khulna", "Daulatpur", "দৌলতপুর", "22.882600", "89.516000"),
    ("Khulna", "Boyra", "বয়রা", "22.836000", "89.539000"),
    ("Khulna", "Gollamari", "গল্লামারী", "22.800000", "89.533000"),
    ("Khulna", "Nirala", "নিরালা", "22.808300", "89.556200"),
    ("Khulna", "Shibbari", "শিববাড়ী", "22.818600", "89.551400"),
    ("Khulna", "Dakbangla", "ডাকবাংলো", "22.818900", "89.565800"),
    ("Khulna", "Moylapota", "ময়লাপোতা", "22.813600", "89.556900"),
    ("Khulna", "Tutpara", "টুটপাড়া", "22.807500", "89.568300"),
    ("Khulna", "Labanchara", "লবণচরা", "22.787800", "89.565400"),
    ("Khulna", "Rupsha", "রূপসা", "22.800900", "89.588900"),
    ("Khulna", "Khan Jahan Ali", "খান জাহান আলী", "22.920200", "89.483600"),
    ("Khulna", "Fulbari Gate", "ফুলবাড়ীগেট", "22.896300", "89.505400"),
    ("Khulna", "Rayermahal", "রায়েরমহল", "22.842500", "89.523900"),
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


def order(token, phone, name, items, area, when=TODAY, slot="11-13", problem="", address="বাড়ি ১২, রোড ৭"):
    """Put the items in the customer's cart and check out (cash on delivery)."""
    for old in call("GET", "/api/cart/", token, expect=200)["items"]:  # a half-finished earlier run
        call("DELETE", f"/api/cart/items/{old['id']}/", token)
    details = {}
    for kind, slug, qty in items:
        ci = call("POST", "/api/cart/items/", token, {"item_type": kind, "slug": slug, "quantity": qty}, expect=201)
        if kind == "service":
            details[str(ci["id"])] = {"scheduled_date": when.isoformat(), "slot": slot, "problem_description": problem}
    return call("POST", "/api/orders/", token, {
        "contact_name": name, "contact_phone": phone, "address_line": address, "area_id": area["id"],
        "area_name": area["name_bn"], "latitude": area["lat"], "longitude": area["lng"], "service_details": details,
    }, expect=201)

def take(provider, o, finish=True, photo="ai-samples/burnt-socket.jpg", note="সুইচবোর্ড বদলে দেওয়া হয়েছে"):
    """The provider accepts the booking's job and, unless finish=False, does it with the arrival code and a photo."""
    b = o["bookings"][0]
    job = wait_for(lambda: next((j for j in call("GET", "/api/providers/jobs/?tab=available", provider)["results"]
                                 if j["source"] == "booking" and j["source_id"] == b["id"]), None), "job in inbox", timeout=30)
    call("POST", f"/api/providers/jobs/{job['id']}/accept/", provider, expect=200)
    if finish:
        call("PATCH", f"/api/providers/jobs/{job['id']}/status/", provider, {"status": "on_the_way"}, expect=200)
        call("PATCH", f"/api/providers/jobs/{job['id']}/status/", provider,
             {"status": "working", "arrival_code": b["arrival_code"], "photos": [f"{IMG}/{photo}"]}, expect=200)
        call("PATCH", f"/api/providers/jobs/{job['id']}/status/", provider, {"status": "completed", "note": note}, expect=200)
    return job, b


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
    city_ids = {city: [areas[a[1]]["id"] for a in AREAS if a[0] == city] for city in {a[0] for a in AREAS}}
    customers = {p: register(p, n) for p, n in CUSTOMERS}
    # a saved home address for every demo customer, so checkout and subscriptions start filled in
    for phone, (area, line) in HOME_ADDRESSES.items():
        token = customers[phone]["access"]
        if not call("GET", "/api/me/addresses/", token, expect=200):
            call("POST", "/api/me/addresses/", token, {"label": "বাসা", "area": areas[area]["id"], "line": line,
                                                       "latitude": areas[area]["lat"], "longitude": areas[area]["lng"], "is_default": True}, expect=201)
    step(f"admin {ADMIN[0]}, {len(areas)} areas in Dhaka, Chattogram and Khulna, {len(customers)} customers")

    # 2. Providers: apply, admin approves, online with emergency contact
    providers = {}
    for p_phone, p_name, p_type, skills, gender in PROVIDERS:
        tokens = register(p_phone, p_name)
        if role_of(tokens["access"]) != "provider":
            call("POST", "/api/providers/register/", tokens["access"], {
                "provider_type": p_type, "skills": skills, "area_ids": city_ids["Khulna" if p_phone in KHULNA_PROVIDERS else "Dhaka"], "nid_number": "19901234567890",
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
    step(f"{len(providers)} providers approved and online (3 in Dhaka, {len(KHULNA_PROVIDERS)} in Khulna)")

    # 3. Orders: a finished electrician job with review, a confirmed AC booking, a product order, a pending cleaning job
    rahim, nusrat = customers["01711000001"]["access"], customers["01711000002"]["access"]
    dh = areas["Dhanmondi"]

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
        reporter = reporters[i % 3]
        issue = call("POST", "/api/issues/", reporter, {
            "category": cat, "title": title, "description": desc, "latitude": a["lat"], "longitude": a["lng"], "area_id": a["id"],
            "area_name": a["name_bn"], "photo_urls": [f"{IMG}/issues/{photo}"], "force": True}, expect=201)
        for other in reporters:
            if other is not reporter:  # the reporter's own vote is already counted; upvote toggles
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
    step("Dhaka: 2 authorities with feed links, 4 photo issues (one resolved), 3 community posts")

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

    # 8. Khulna: its own providers, customers, orders, city issues, offers
    khulna(admin, areas, customers, providers, services)

    # 9. Synthetic analytics history for the insight tabs
    sh("docker", "compose", "cp", "scripts/demo_analytics_history.py", "analytics:/tmp/demo_history.py")
    out = sh("docker", "compose", "exec", "-T", "analytics", "python", "manage.py", "shell", "-c", "exec(open('/tmp/demo_history.py').read())")
    step(out.stdout.strip().splitlines()[-1] if out.stdout.strip() else "analytics history added")

    print(f"""
Demo data ready. Password for every account: {PASSWORD}
  admin     {ADMIN[0]}   → admin panel
  Dhaka     customers 01711000001 (রহিম, tenant in Dhanmondi) · 01711000002 (নুসরাত) · 01711000003 (তানভীর)
            providers 01811000001 (electrician) · 01811000002 (female cleaner) · 01811000003 (AC technician)
  Khulna    customers 01711000004 (ফারহানা) · 01711000005 (আরিফ) · 01711000006 (সুমাইয়া) · 01711000007 (রাকিব) · 01711000008 (তাসলিমা)
            providers 01811000004 (electrician) · 01811000005 (female cleaner) · 01811000006 (AC & plumbing) · 01811000007 (painter & shifting)
""")



# Khulna: every area has something, and every kind of city problem and service shows up at least once.
KHULNA_AUTHORITIES = {
    # key: (Bangla name, English name, issue categories it handles)
    "kcc_cons": ("খুলনা সিটি কর্পোরেশন, পরিচ্ছন্নতা বিভাগ", "Khulna City Corporation, Conservancy", ["garbage"]),
    "kcc_eng": ("খুলনা সিটি কর্পোরেশন, প্রকৌশল বিভাগ", "Khulna City Corporation, Engineering", ["streetlight", "road_damage", "drainage"]),
    "kcc_health": ("খুলনা সিটি কর্পোরেশন, স্বাস্থ্য বিভাগ (মশক নিধন)", "Khulna City Corporation, Health (mosquito control)", ["mosquito"]),
    "kwasa": ("খুলনা ওয়াসা", "Khulna WASA", ["waterlogging", "water_supply"]),
    "wzpdcl": ("ওজোপাডিকো, খুলনা", "WZPDCL Khulna (power lines)", ["other"]),
}
# category, title, description, area, photo, authority, final status, how many neighbours upvote (0-4)
KHULNA_ISSUES = [
    ("waterlogging", "সোনাডাঙ্গা বাসস্ট্যান্ডে পানি জমে", "জোয়ার আর বৃষ্টিতে ড্রেন উপচে রাস্তা ডুবে যায়, বাস ঢুকতে পারে না।", "Sonadanga", "khulna-waterlogging.jpg", "kwasa", "in_progress", 4),
    ("waterlogging", "রায়েরমহলে বৃষ্টির পানি নামে না", "এক ঘণ্টার বৃষ্টিতে স্কুলের সামনে হাঁটুপানি জমে থাকে।", "Rayermahal", "waterlogging.jpg", "kwasa", "forwarded", 2),
    ("garbage", "খালিশপুরে ময়লার কন্টেইনার উপচে পড়ছে", "ক্রিসেন্ট জুট মিলের সামনে চার দিন ধরে ময়লা নেওয়া হয়নি।", "Khalishpur", "khulna-garbage.jpg", "kcc_cons", "forwarded", 3),
    ("garbage", "ময়লাপোতা মোড়ে খোলা ভাগাড়", "বাজারের পাশে খোলা জায়গায় ময়লা ফেলা হচ্ছে, কুকুর-কাক ছড়িয়ে দেয়।", "Moylapota", "garbage.jpg", "kcc_cons", "resolved", 4),
    ("streetlight", "বয়রা কলোনির গলিতে বাতি নেই", "সন্ধ্যার পর পুরো গলি অন্ধকার, মেয়েদের চলাচলে ভয়।", "Boyra", "khulna-streetlight.jpg", "kcc_eng", "resolved", 3),
    ("streetlight", "লবণচরা বেড়িবাঁধ রোডে বাতি জ্বলে না", "নদীর ধারের রাস্তায় তিনটা পোল অন্ধকার।", "Labanchara", "streetlight.jpg", None, "reported", 1),
    ("road_damage", "দৌলতপুর-খুলনা রোডে ভাঙা রাস্তা", "কুয়েট গেটের কাছে রাস্তা ভেঙে বড় গর্ত, ইজিবাইক উল্টে যাচ্ছে।", "Daulatpur", "khulna-road.jpg", None, "reported", 4),
    ("road_damage", "খান জাহান আলী রোডে কার্পেটিং উঠে গেছে", "শিরোমণি থেকে আটরা পর্যন্ত রাস্তায় খানাখন্দ।", "Khan Jahan Ali", "road.jpg", "kcc_eng", "in_progress", 2),
    ("drainage", "গল্লামারীতে ড্রেন বন্ধ", "ড্রেনের মুখ আটকে পানি বাসার সামনে জমে থাকে।", "Gollamari", "khulna-drain.jpg", "kcc_eng", "in_progress", 3),
    ("drainage", "টুটপাড়া কবরখানা রোডের ড্রেনে স্ল্যাব নেই", "খোলা ড্রেনে রাতে মানুষ পড়ে যাচ্ছে।", "Tutpara", "khulna-drain.jpg", "kcc_eng", "forwarded", 2),
    ("mosquito", "নিরালায় মশার উপদ্রব, ডেঙ্গুর ভয়", "লেকের পানিতে মশার লার্ভা, এক মাসে দুজন ডেঙ্গু রোগী।", "Nirala", "khulna-mosquito.jpg", "kcc_health", "in_progress", 4),
    ("mosquito", "শিববাড়ী মোড়ে জমা পানিতে লার্ভা", "পরিত্যক্ত টায়ার আর ড্রামে পানি জমে আছে।", "Shibbari", "khulna-mosquito.jpg", None, "reported", 1),
    ("water_supply", "ফুলবাড়ীগেটে তিন দিন ওয়াসার পানি নেই", "পাইপলাইন মেরামতের পর থেকে পানি আসছে না, টিউবওয়েলে লাইন।", "Fulbari Gate", "khulna-water-supply.jpg", "kwasa", "forwarded", 3),
    ("water_supply", "রূপসা ঘাট এলাকায় পানিতে লবণ", "কলের পানি নোনা, খাওয়া যায় না।", "Rupsha", "khulna-water-supply.jpg", "kwasa", "resolved", 2),
    ("other", "ডাকবাংলো মোড়ে বিদ্যুতের তারের জট", "পোলে ঝুলন্ত তার নিচে নেমে এসেছে, বৃষ্টিতে স্পার্ক করে।", "Dakbangla", "khulna-wires.jpg", "wzpdcl", "in_progress", 3),
    ("other", "লবণচরায় ফুটপাত দখল", "ফুটপাতে দোকান বসে, মানুষ রাস্তায় হাঁটতে বাধ্য হয়।", "Labanchara", "road.jpg", None, "rejected", 0),
]
KHULNA_REJECT_NOTE = "ফুটপাত দখল উচ্ছেদ সিটি কর্পোরেশনের এস্টেট বিভাগ সরাসরি দেখে; তাদের হটলাইনে জানান।"
KHULNA_RESOLVED_NOTES = {
    "garbage": "ভাগাড় সরিয়ে ঢাকনাসহ কন্টেইনার বসানো হয়েছে",
    "streetlight": "নতুন এলইডি স্ট্রিটলাইট লাগানো হয়েছে",
    "water_supply": "লবণাক্ততা পরীক্ষা করে লাইন বদলানো হয়েছে",
}


def khulna(admin, areas, customers, providers, services):
    c = {p: customers[p]["access"] for p in ("01711000004", "01711000005", "01711000006", "01711000007", "01711000008")}
    farhana, arif, sumaiya, rakib, taslima = c.values()
    masud, rehana, saiful, nazmul = (providers[p] for p in ("01811000004", "01811000005", "01811000006", "01811000007"))
    names = {farhana: ("01711000004", "ফারহানা ইসলাম"), arif: ("01711000005", "আরিফ হাসান"), sumaiya: ("01711000006", "সুমাইয়া আক্তার"),
             rakib: ("01711000007", "রাকিব হাসান"), taslima: ("01711000008", "তাসলিমা খাতুন")}
    homes = {farhana: ("Sonadanga", "বাড়ি ৩৪, মজিদ সরণি"), arif: ("Khalishpur", "হাউজিং এস্টেট, ব্লক বি"),
             sumaiya: ("Boyra", "বয়রা মেইন রোড, বাড়ি ৯"), rakib: ("Nirala", "নিরালা আবাসিক, রোড ১৩"),
             taslima: ("Dakbangla", "কে ডি ঘোষ রোড, বাড়ি ২১")}

    def book(who, slug, *, days=0, slot="11-13", problem="", qty=1, kind="service"):
        area, address = homes[who]
        phone, name = names[who]
        return order(who, phone, name, [(kind, slug, qty)], areas[area], when=TODAY + timedelta(days=days), slot=slot,
                     problem=problem, address=address)

    # services: one or more bookings for every service category, in different states
    done = []  # (order, customer, rating, comment)
    for who, slug, provider, photo, note, problem, rating, comment in [
        (farhana, "electrician-visit", masud, "ai-samples/burnt-socket.jpg", "ফ্যানের রেগুলেটর ও ক্যাপাসিটর বদলানো হয়েছে",
         "ফ্যান ঘুরছে না, রেগুলেটর গরম হয়ে যায়", 5, "খুলনায় এত দ্রুত সার্ভিস আগে পাইনি।"),
        (arif, "ac-cleaning", saiful, "ai-samples/ac-leak.jpg", "ইনডোর ও আউটডোর ইউনিট জেট ওয়াশ করা হয়েছে",
         "এসি চালালে পানি পড়ে", 4, "সময়মতো এসেছেন, কাজ পরিষ্কার।"),
        (rakib, "cockroach-control", rehana, "services/cockroach-control.jpg", "রান্নাঘর ও বাথরুমে জেল দেওয়া হয়েছে",
         "রান্নাঘরে তেলাপোকা খুব বেশি", 5, "এক সপ্তাহেই তেলাপোকা নেই, আপা খুব যত্ন করে কাজ করেছেন।"),
        (taslima, "appliance-repair", masud, "services/appliance-repair.jpg", "ফ্রিজের থার্মোস্ট্যাট বদলানো হয়েছে",
         "ফ্রিজ ঠান্ডা হচ্ছে না", 4, "দাম আগেই বলে দিয়েছেন, কোনো লুকানো খরচ নেই।"),
        (rakib, "ac-gas-refill", saiful, "ai-samples/ac-leak.jpg", "লিক সারিয়ে গ্যাস ভরা হয়েছে",
         "এসি ঠান্ডা কম দিচ্ছে", 5, "গ্যাস ভরার আগে লিক খুঁজে বের করেছেন, ভালো লাগল।"),
        (arif, "basin-sink-repair", saiful, "ai-samples/pipe-leak.jpg", "সিংকের ট্র্যাপ ও পাইপ বদলানো হয়েছে",
         "সিংকের নিচে পানি জমে", 3, "কাজ ভালো, তবে এক ঘণ্টা দেরিতে এসেছেন।"),
    ]:
        o = book(who, slug, problem=problem)
        take(provider, o, photo=photo, note=note)
        done.append((o, who, rating, comment))
    for o, who, rating, comment in done:
        wait_for(lambda: call("GET", f"/api/orders/{o['id']}/", who)["bookings"][0]["status"] == "completed", "Khulna job completed")
        call("POST", "/api/providers/reviews/", who, {"source": "booking", "source_id": o["bookings"][0]["id"], "rating": rating, "comment": comment})
    for who, slug, provider, days, slot in [(sumaiya, "home-deep-clean", rehana, 1, "09-11"), (taslima, "wall-painting", nazmul, 3, "09-11"),
                                            (rakib, "house-shifting", nazmul, 5, "09-11")]:
        take(provider, book(who, slug, days=days, slot=slot), finish=False)
    # waiting in the Khulna providers' "new jobs" inbox
    book(arif, "plumber-visit", days=2, slot="16-18", problem="বাথরুমের কমোডে পানি আটকে যায়")
    book(sumaiya, "mosquito-fogging", days=1, slot="18-20", problem="বাসার পেছনে ঝোপে খুব মশা")
    book(taslima, "kitchen-deep-clean", days=2, slot="14-16")
    book(farhana, "ceiling-fan-56", kind="product")
    book(rakib, "extension-board-4", kind="product", qty=2)
    for p in (rehana, masud):
        call("POST", "/api/providers/training/safety-conduct/submit/", p, {"answers": [0, 0]})
    step("Khulna: 14 orders across every service type (6 done and reviewed, 3 confirmed, 3 waiting for a provider, 2 product orders)")

    # subscriptions, custom requests, home profiles
    call("POST", "/api/subscriptions/", sumaiya, {
        "plan": "cleaning-basic", "duration_days": 30, "home_size": 2, "start_date": (TODAY + timedelta(days=2)).isoformat(),
        "preferred_weekday": (TODAY + timedelta(days=2)).weekday(), "slot": "09-11", "area_id": areas["Boyra"]["id"],
        "area_name": areas["Boyra"]["name_bn"], "address_line": homes[sumaiya][1], "payment_method": "cod", "prefer_female": True})
    for who, service_type, description, quote in [
        (arif, "আইপিএস ব্যাটারি বদল ও ওয়্যারিং", "পুরনো ব্যাটারি বদলে নতুন ১৫০Ah, দুই রুমে আলাদা লাইন",
         {"labor": "1500", "materials": "16500", "transport": "300", "platform_fee": "500", "category_slug": "electrical"}),
        (rakib, "ছাদের পানির ট্যাংক পরিষ্কার", "১০০০ লিটারের দুটি প্লাস্টিক ট্যাংক, ব্লিচিংসহ", None),
        (taslima, "বাথরুমের টাইলস বদল", "একটি বাথরুমের মেঝে ও দেয়ালের ভাঙা টাইলস", None),
    ]:
        area, address = homes[who]
        req = call("POST", "/api/custom-requests/", who, {
            "service_type": service_type, "description": description, "area_id": areas[area]["id"], "area_name": areas[area]["name_bn"],
            "address_line": address, "preferred_date": (TODAY + timedelta(days=4)).isoformat()}, expect=201)
        if quote:
            call("PATCH", f"/api/admin/custom-requests/{req['id']}/quote/", admin, quote)
    call("POST", "/api/home-profiles/", sumaiya, {
        "name": "বয়রার বাসা", "address": "বয়রা মেইন রোড, বাড়ি ৯, খুলনা", "area": areas["Boyra"]["id"], "property_type": "house",
        "square_feet": 1800, "ac_count": 2, "water_purifier": True, "wiring_age_years": 15, "plumbing_age_years": 11, "occupancy_mode": "owner"},
        expect=201)
    call("POST", "/api/home-profiles/", taslima, {
        "name": "ডাকবাংলোর ফ্ল্যাট", "address": "কে ডি ঘোষ রোড, বাড়ি ২১, খুলনা", "area": areas["Dakbangla"]["id"], "property_type": "apartment",
        "square_feet": 1100, "ac_count": 1, "water_purifier": True, "wiring_age_years": 8, "plumbing_age_years": 8, "occupancy_mode": "tenant",
        "landlord_name": "মোস্তফা কামাল", "landlord_phone": "01799000111"}, expect=201)
    step("Khulna: cleaning subscription, 3 custom requests (1 quoted), 2 home profiles")

    # city problems: every category, every area, every status
    auths = {}
    for key, (bn, en, cats) in KHULNA_AUTHORITIES.items():
        auths[key] = call("POST", "/api/admin/authorities/", admin, {"name_bn": bn, "name_en": en, "categories": cats}, expect=201)
        call("POST", f"/api/admin/authorities/{auths[key]['id']}/rotate-feed/", admin, expect=200)
    people = list(names)
    for i, (cat, title, desc, area, photo, authority, status, upvotes) in enumerate(KHULNA_ISSUES):
        a = areas[area]
        reporter = people[i % len(people)]
        # a little apart so two reports in one area are not taken for duplicates
        lat, lng = f"{float(a['lat']) + 0.0012 * (i % 3):.6f}", f"{float(a['lng']) - 0.0011 * (i % 2):.6f}"
        issue = call("POST", "/api/issues/", reporter, {
            "category": cat, "title": title, "description": desc, "latitude": lat, "longitude": lng, "area_id": a["id"],
            "area_name": a["name_bn"], "landmark": a["name_bn"], "photo_urls": [f"{IMG}/issues/{photo}"], "force": True}, expect=201)
        for other in [p for p in people if p is not reporter][:upvotes]:
            call("POST", f"/api/issues/{issue['id']}/upvote/", other)
        if status == "rejected":
            call("POST", f"/api/admin/issues/{issue['id']}/status/", admin, {"status": "rejected", "note": KHULNA_REJECT_NOTE}, expect=200)
            continue
        if authority:
            call("POST", f"/api/admin/issues/{issue['id']}/status/", admin, {"status": "forwarded", "authority": auths[authority]["id"]}, expect=200)
        if status in ("in_progress", "resolved"):
            call("POST", f"/api/admin/issues/{issue['id']}/status/", admin, {"status": "in_progress", "note": "কাজ শুরু হয়েছে"}, expect=200)
        if status == "resolved":
            call("POST", f"/api/admin/issues/{issue['id']}/status/", admin, {"status": "resolved", "note": KHULNA_RESOLVED_NOTES[cat]}, expect=200)
    for who, area, kind, body in [
        (farhana, "Sonadanga", "recommendation", "মাসুদ ভাই খুব ভালো ইলেকট্রিশিয়ান, ফ্যানের কাজ আধা ঘণ্টায় শেষ করেছেন।"),
        (arif, "Khalishpur", "alert", "আগামীকাল সকাল ৯টা থেকে ১২টা খালিশপুরে বিদ্যুৎ থাকবে না (ওজোপাডিকো)।"),
        (sumaiya, "Boyra", "question", "বয়রায় পানির ট্যাংক পরিষ্কার কে ভালো করেন?"),
        (arif, "Daulatpur", "tip", "বর্ষার আগে ছাদের ড্রেন পরিষ্কার করিয়ে নিন, খরচ কম পড়ে।"),
        (rakib, "Nirala", "alert", "নিরালা লেকের পাশে আজ বিকেল ৪টায় সিটি কর্পোরেশনের মশক নিধন ফগিং হবে।"),
        (taslima, "Dakbangla", "recommendation", "নাজমুল ভাই রং করার কাজে খুব পরিষ্কার, ফার্নিচার ঢেকে কাজ করেন।"),
        (rakib, "Rupsha", "tip", "রূপসায় কলের পানি নোনা লাগলে ওয়াসার হটলাইন ১৬১৬২-তে জানান।"),
        (farhana, "Shibbari", "question", "শিববাড়ী মোড়ের কাছে ভালো এসি সার্ভিসিং কোথায় হয়?"),
        (taslima, "Fulbari Gate", "alert", "ফুলবাড়ীগেটে পাইপলাইনের কাজ চলছে, দুই দিন পানি কম আসবে।"),
    ]:
        call("POST", "/api/community/posts/", who, {"area_id": areas[area]["id"], "area_name": areas[area]["name_bn"], "kind": kind, "body": body}, expect=201)
    step(f"Khulna: {len(KHULNA_AUTHORITIES)} authorities with feed links, {len(KHULNA_ISSUES)} photo issues of all 8 kinds in "
         f"{len({i[3] for i in KHULNA_ISSUES})} areas, 9 community posts")

    # offers: a Khulna monsoon package, two group deals, a sponsored listing
    call("POST", "/api/seasonal-packages/", admin, {
        "title_bn": "খুলনায় বর্ষার প্রস্তুতি", "title_en": "Khulna monsoon ready", "season": "monsoon",
        "tagline_bn": "জোয়ার-বৃষ্টির আগে প্লাম্বিং, ড্রেন আর মশা নিয়ন্ত্রণ", "tagline_en": "Plumbing, drains and mosquitoes before the tide and rain",
        "service_slugs": ["plumber-visit", "basin-sink-repair", "mosquito-fogging"], "discount_percent": 12,
        "banner_image_url": f"{IMG}/banners/khulna-river.jpg",
        "active_from": (TODAY - timedelta(days=2)).isoformat(), "active_until": (TODAY + timedelta(days=45)).isoformat()}, expect=201)
    for title_bn, title_en, slug, area, target, pct, joiners in [
        ("খালিশপুর হাউজিং: এসি ক্লিনিং গ্রুপ ডিল", "Khalishpur Housing: AC cleaning group deal", "ac-cleaning", "Khalishpur", 5, 20, [farhana, arif, sumaiya]),
        ("নিরালা আবাসিক: তেলাপোকা নিয়ন্ত্রণ গ্রুপ ডিল", "Nirala R/A: cockroach control group deal", "cockroach-control", "Nirala", 4, 25, [rakib, taslima]),
    ]:
        deal = call("POST", "/api/group-deals/", admin, {
            "title_bn": title_bn, "title_en": title_en, "service": services[slug]["id"], "target_participants": target, "discount_percent": pct,
            "area_ids": [areas[area]["id"]], "expires_at": f"{(TODAY + timedelta(days=12)).isoformat()}T18:00:00+06:00"}, expect=201)
        for who in joiners:
            call("POST", f"/api/group-deals/{deal['id']}/join/", who, expect=200)
    call("POST", "/api/services/ceiling-fan-installation/sponsor/", admin,
         {"days": 10, "fee": "1500", "sponsor_name": "খুলনা ইলেকট্রিক হাউস, ডাকবাংলো"}, expect=201)
    step("Khulna: monsoon package with a Khulna photo, 2 group deals, sponsored fan installation")

if __name__ == "__main__":
    t = time.time()
    main()
    print(f"done in {time.time() - t:.0f}s")
