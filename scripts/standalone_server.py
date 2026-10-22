"""ShohorSathi without Docker: one Python process that stands in for the whole backend, for demos on any laptop.

    python scripts/standalone_server.py [port]        (default 8088; standard library only, Python 3.8+)
    pnpm dev                                          (the three apps, in another terminal)

Pages show the real demo data: every API answer the apps get was recorded from the real Docker backend
(scripts/standalone/record_snapshot.mjs → demo/data/standalone_snapshot.json) and is replayed here per user.
The demo actions work too and are kept in memory until the server stops: cart, checkout (cash, bKash, Nagad, card
through a mock payment page), cancelling and rescheduling, reviews, saved addresses, city-problem reports with photos,
upvotes, community posts, custom requests and quotes, subscriptions, the home profile, the AI quote, notifications,
providers accepting and doing jobs, and the admin quoting requests and forwarding city problems.
Any other change is accepted and echoed back. This is a demo stand-in, not the backend: there is no real database,
no background jobs and no chat server. Accounts: the demo accounts (password demo1234); new sign-ups use OTP 123456.
"""
import base64
import copy
import email.parser
import email.policy
import http.server
import json
import mimetypes
import pathlib
import random
import re
import socketserver
import sys
import threading
import time
import urllib.parse
from datetime import date, datetime, timedelta

ROOT = pathlib.Path(__file__).resolve().parent.parent
SNAPSHOT = ROOT / "demo" / "data" / "standalone_snapshot.json"
UPLOADS = ROOT / ".standalone_uploads"
PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8088
CUSTOMER_WEB = "http://localhost:5173"
PASSWORD = "demo1234"
DEMO_OTP = "123456"

if not SNAPSHOT.exists():
    sys.exit(f"Missing {SNAPSHOT}. It is part of the repository; pull the latest version.")
SNAP = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
BODIES, ROUTES, USERS = SNAP["bodies"], SNAP["routes"], SNAP["users"]
OVERRIDES = {}  # user -> {route key -> body}, every change made while the server runs
CARTS, PAYMENTS, UPVOTES, LIKES, COMMENTS, SHARES = {}, {}, {}, {}, {}, {}
LOCK = threading.RLock()
_next = [900000]


def next_id():
    _next[0] += 1
    return _next[0]


def now():
    return datetime.now().astimezone().isoformat()


# ---------------------------------------------------------------- route store

def route_key(path, query):
    pairs = sorted(urllib.parse.parse_qsl(query, keep_blank_values=True))
    return path + ("?" + urllib.parse.urlencode(pairs) if pairs else "")


SEGMENTS = {seg for r in ROUTES.values() for k in r for seg in k.split("?")[0].split("/")}


def known_users():
    return set(ROUTES) | set(OVERRIDES)


def keys_of(user):
    return set(ROUTES.get(user, {})) | set(OVERRIDES.get(user, {}))


def raw(user, key):
    if key in OVERRIDES.get(user, {}):
        return OVERRIDES[user][key]
    h = ROUTES.get(user, {}).get(key)
    return BODIES[h] if h else None


def put(user, key, body):
    OVERRIDES.setdefault(user, {})[key] = body


def lookup(user, key):
    """This user's recorded answer, else the visitor's, else a list recorded for the same path with other query parameters."""
    for u in (user, "guest"):
        b = raw(u, key)
        if b is not None:
            return copy.deepcopy(b)
    path = key.split("?")[0]
    for u in (user, "guest"):
        variants = sorted((k for k in keys_of(u) if k.split("?")[0] == path), key=len)
        if variants and items_of(raw(u, variants[0])) is not None:
            return copy.deepcopy(raw(u, variants[0]))
    return None


def edit(key_path, fn, users=None):
    """Apply fn(body) -> body to every recorded answer for this path (any query), for the given users (default: all)."""
    for u in list(users or known_users()):
        for k in [k for k in keys_of(u) if k.split("?")[0] == key_path]:
            b = copy.deepcopy(raw(u, k))
            nb = fn(b, k)
            if nb is not None:
                put(u, k, nb)


def items_of(body):
    return body["results"] if isinstance(body, dict) and "results" in body else body if isinstance(body, list) else None


def prepend(key_path, obj, users=None, keep=None):
    def fn(b, k):
        lst = items_of(b)
        if lst is None or (keep and not keep(k)):
            return None
        lst.insert(0, copy.deepcopy(obj))
        if isinstance(b, dict) and "count" in b:
            b["count"] += 1
        return b
    edit(key_path, fn, users)


def update_everywhere(match, change, prefixes):
    """Change every object (in lists and detail answers under these paths) for which match(obj) is true."""
    def walk(b, _k):
        hit = [False]

        def visit(o):
            if isinstance(o, dict):
                if match(o):
                    change(o)
                    hit[0] = True
                for v in o.values():
                    visit(v)
            elif isinstance(o, list):
                for v in o:
                    visit(v)
        visit(b)
        return b if hit[0] else None
    for u in list(known_users()):
        for k in list(keys_of(u)):
            if any(k.startswith(p) for p in prefixes):
                b = copy.deepcopy(raw(u, k))
                nb = walk(b, k)
                if nb is not None:
                    put(u, k, nb)


def template(predicate):
    """A recorded object with the right shape, to build new ones from."""
    for b in BODIES.values():
        for o in (items_of(b) or [b]):
            if isinstance(o, dict) and predicate(o):
                return copy.deepcopy(o)
    return {}


def fill(tpl, values):
    out = {k: None for k in tpl}
    for k, v in tpl.items():
        if isinstance(v, list):
            out[k] = []
        elif isinstance(v, str):
            out[k] = ""
        elif isinstance(v, bool):
            out[k] = False
        elif isinstance(v, (int, float)):
            out[k] = 0
    out.update(values)
    return out


def money(x):
    return f"{float(x):.2f}"


# ---------------------------------------------------------------- auth

def b64(data):
    return base64.urlsafe_b64encode(data).decode().rstrip("=")


def make_token(claims, kind):
    body = {**claims, "token_type": kind, "exp": int(time.time()) + (86400 * 30 if kind == "refresh" else 86400), "iat": int(time.time())}
    return f'{b64(json.dumps({"alg": "none", "typ": "JWT"}).encode())}.{b64(json.dumps(body).encode())}.standalone'


def read_token(token):
    try:
        part = token.split(".")[1]
        return json.loads(base64.urlsafe_b64decode(part + "=" * (-len(part) % 4)))
    except Exception:
        return None


def tokens_for(phone):
    c = USERS[phone]["tokens_claims"]
    claims = {"user_id": c["user_id"], "role": c["role"], "name": c["name"], "phone": c["phone"]}
    return {"access": make_token(claims, "access"), "refresh": make_token(claims, "refresh")}


# ---------------------------------------------------------------- domain helpers

def areas():
    for k in keys_of("guest"):
        if k.startswith("/api/areas/"):
            for a in raw("guest", k):
                yield a


def area(area_id):
    return next((a for a in areas() if a["id"] == int(area_id)), {"id": area_id, "name_bn": "", "name_en": "", "city": "", "ward": ""})


def catalog(kind, slug):
    return lookup("guest", f"/api/{kind}s/{slug}/") or {}


def cart_body(user):
    items = CARTS.get(user, [])
    return {"items": items, "subtotal": money(sum(float(i["line_total"]) for i in items))}


def user_orders(user):
    return items_of(lookup(user, "/api/orders/")) or []


def find_booking(booking_id):
    for u in known_users():
        for o in items_of(raw(u, "/api/orders/")) or []:
            for b in o.get("bookings", []):
                if b["id"] == int(booking_id):
                    return u, o, b
    return None, None, None


def save_order(user, order):
    put(user, f"/api/orders/{order['id']}/", order)

    def fn(b, _k):
        lst = items_of(b)
        for i, o in enumerate(lst):
            if o["id"] == order["id"]:
                lst[i] = copy.deepcopy(order)
                return b
        return None
    edit("/api/orders/", fn, [user])


def track(booking_id, status, note=""):
    owner, order, _ = find_booking(booking_id)
    if order:
        t = lookup(owner, f"/api/orders/{order['id']}/tracking/") or {"status": status, "events": []}
        t["status"] = status
        t["events"].append({"status": status, "note": note, "booking": int(booking_id), "created_at": now()})
        put(owner, f"/api/orders/{order['id']}/tracking/", t)


def job_by_booking(booking_id):
    for u in known_users():
        for k in keys_of(u):
            if k.startswith("/api/providers/jobs/"):
                for j in items_of(raw(u, k)) or ([raw(u, k)] if isinstance(raw(u, k), dict) else []):
                    if isinstance(j, dict) and j.get("source") == "booking" and j.get("source_id") == int(booking_id):
                        return j
    return None


def provider_users(city):
    """Demo providers who work in this city (by the areas in their recorded profile)."""
    city_ids = {a["id"] for a in areas() if a["city"] == city}
    for phone, u in USERS.items():
        if u["tokens_claims"]["role"] != "provider":
            continue
        me = raw(phone, "/api/providers/me/")
        if me and set(me.get("area_ids", [])) & city_ids:
            yield phone


# ---------------------------------------------------------------- AI quote (same rules as the backend's keyword fallback)

KEYWORDS = [
    ("ac", ["এসি", "ঠান্ডা", "কুলিং", "গ্যাস", "cooling", "ac "], "medium", "এসির কয়েল পরিষ্কার ও গ্যাস প্রেশার চেক করতে হবে। পানি পড়লে এসি বন্ধ রাখুন।"),
    ("plumbing", ["পাইপ", "পানি", "লিক", "কল", "বেসিন", "টয়লেট", "ড্রেন", "pipe", "leak", "tap", "sink", "drain"], "high", "পানির মেইন লাইনের চাবি বন্ধ করে রাখুন, প্লাম্বার এসে ফিটিংস বদলাবেন।"),
    ("electrical", ["সুইচ", "শর্ট", "কারেন্ট", "ফ্যান", "তার", "লাইট", "spark", "switch", "short", "fan", "wiring"], "critical", "মেইন সুইচ বন্ধ রাখুন এবং নিজে হাত দেবেন না।"),
    ("cleaning", ["ময়লা", "পরিষ্কার", "সোফা", "কার্পেট", "দাগ", "clean", "dirty", "stain"], "low", "ক্লিনার এসে মেশিন দিয়ে গভীরভাবে পরিষ্কার করবেন।"),
    ("pest-control", ["তেলাপোকা", "ইঁদুর", "পোকা", "উইপোকা", "মশা", "cockroach", "rat", "termite", "pest"], "medium", "খাবার ঢেকে রাখুন; ট্রিটমেন্টের সময় শিশু ও পোষা প্রাণী সরিয়ে রাখবেন।"),
]


def ai_quote(user, body):
    text = f" {(body.get('description') or '').lower()} "
    services = items_of(lookup("guest", "/api/services/")) or []
    cat, severity, action = None, "medium", "প্রোভাইডার এসে দেখে সঠিক খরচ জানাবেন।"
    for c, words, sev, act in KEYWORDS:
        if any(w in text for w in words):
            cat, severity, action = c, sev, act
            break
    service = next((s for s in services if s.get("category_slug") == cat), None) or next((s for s in services if s["slug"] == "electrician-visit"), services[0])
    base = float(service["base_price"])
    return {"id": next_id(), "user_id": None, "photo_url": body.get("photo_url", ""), "description": body.get("description", ""),
            "detected_category": cat or service.get("category_slug", "general"), "detected_issue": "বিবরণ থেকে আনুমানিক সমস্যা — প্রোভাইডার এসে নিশ্চিত করবেন",
            "recommended_service_slug": service["slug"], "recommended_service_name_bn": service["name_bn"], "estimated_min_price": money(base),
            "estimated_max_price": money(round(base * 2.5)), "confidence": "0.50" if cat else "0.20", "severity": severity,
            "suggested_action": action, "engine": "keywords", "created_at": now()}


# ---------------------------------------------------------------- actions

def place_order(user, body):
    cart = CARTS.get(user, [])
    if not cart:
        return 400, {"cart": ["Your cart is empty."]}
    claims = USERS.get(user, {}).get("tokens_claims", {})
    tpl_order = template(lambda o: "bookings" in o and "items" in o and "number" in o)
    tpl_booking = template(lambda o: "arrival_code" in o and "service_slug" in o)
    tpl_item = template(lambda o: set(o) >= {"slug", "name", "unit_price", "quantity", "line_total"} and "item_type" not in o)
    oid = next_id()
    number = f"SS{date.today():%y%m%d}-{oid % 100000:05d}"
    details = body.get("service_details") or {}
    products = [c for c in cart if c["item_type"] == "product"]
    services = [c for c in cart if c["item_type"] == "service"]
    subtotal = sum(float(c["line_total"]) for c in cart)
    loyalty = lookup(user, "/api/loyalty/me/") or {}
    discount = float(min(int(body.get("redeem_points") or 0), loyalty.get("points", 0), int(subtotal * 0.2)))
    online = body.get("payment_method") == "online"
    bookings = []
    for c in services:
        d = details.get(str(c["id"])) or {}
        slot = d.get("slot", "09-11")
        bookings.append(fill(tpl_booking, {
            "id": next_id(), "order": oid, "order_number": number, "user_id": claims.get("user_id"), "service_slug": c["slug"], "service_name": c["name"],
            "scheduled_date": d.get("scheduled_date", str(date.today() + timedelta(days=1))), "slot": slot,
            "slot_label": {"09-11": "09:00–11:00", "11-13": "11:00–13:00", "14-16": "14:00–16:00", "16-18": "16:00–18:00", "18-20": "18:00–20:00", "20-22": "20:00–22:00"}.get(slot, slot),
            "problem_description": d.get("problem_description", ""), "photo_urls": d.get("photo_urls", []), "is_emergency": bool(d.get("is_emergency")),
            "price": c["unit_price"], "surcharge": "0.00", "status": "pending", "arrival_code": f"{random.randint(0, 9999):04d}",
            "warranty_days": catalog("service", c["slug"]).get("warranty_days", 7), "created_at": now(),
            "required_gender": "female" if d.get("prefer_female") else ""}))
    order = fill(tpl_order, {
        "id": oid, "number": number, "status": "pending", "payment_method": "online" if online else body.get("payment_method", "cod"),
        "payment_status": "unpaid", "subtotal": money(subtotal), "delivery_fee": "0.00", "discount": money(discount),
        "points_redeemed": int(discount), "organization_id": body.get("organization_id"), "total": money(subtotal - discount),
        "contact_name": body.get("contact_name", ""), "contact_phone": body.get("contact_phone", ""), "address_line": body.get("address_line", ""),
        "area_id": body.get("area_id"), "area_name": body.get("area_name", ""), "note": body.get("note", ""),
        "landlord_phone": body.get("landlord_phone", ""), "landlord_approval_status": "pending" if body.get("landlord_phone") else "none",
        "rent_deduction_receipt_number": "", "items": [fill(tpl_item, {"slug": c["slug"], "name": c["name"], "unit_price": c["unit_price"],
                                                                     "quantity": c["quantity"], "line_total": c["line_total"]}) for c in products],
        "bookings": bookings, "created_at": now(), "updated_at": now(), "user_id": claims.get("user_id")})
    if loyalty and discount:
        loyalty["points"] = max(0, loyalty.get("points", 0) - int(discount))
        put(user, "/api/loyalty/me/", loyalty)
    put(user, f"/api/orders/{oid}/", order)
    put(user, f"/api/orders/{oid}/tracking/", {"status": "pending", "events": [{"status": "pending", "note": "Order placed", "created_at": now()}]})
    prepend("/api/orders/", order, [user])
    prepend("/api/admin/orders/", order, ["01700000000"])
    CARTS[user] = []
    # each service becomes a job in the "new jobs" inbox of the providers who work in that city
    city = area(body.get("area_id") or 0).get("city", "")
    tpl_job = template(lambda o: o.get("source") == "booking" and "checklist" in o)
    for b in bookings:
        service = catalog("service", b["service_slug"])
        job = fill(tpl_job, {
            "id": next_id(), "source": "booking", "source_id": b["id"], "title": b["service_name"], "category_slug": service.get("category_slug", ""),
            "area_id": order["area_id"], "area_name": order["area_name"], "address_line": order["address_line"], "customer_name": order["contact_name"],
            "scheduled_date": b["scheduled_date"], "slot": b["slot"], "amount": b["price"], "is_emergency": b["is_emergency"],
            "description": b["problem_description"], "photo_urls": b["photo_urls"], "status": "open", "required_gender": b["required_gender"],
            "customer_score": {"average": None, "count": 0}, "created_at": now(),
            "logs": [{"status": "open", "note": "Job created", "created_at": now()}]})
        for p in provider_users(city):
            put(p, f"/api/providers/jobs/{job['id']}/", job)
            prepend("/api/providers/jobs/", job, [p], keep=lambda k: "tab=available" in k)
        prepend("/api/admin/jobs/", job, ["01700000000"])
    return 201, order


def job_status(user, job_id, body):
    job = lookup(user, f"/api/providers/jobs/{job_id}/")
    if not job:
        return 404, {"detail": "Not found."}
    new = body.get("status")
    _, order, booking = find_booking(job["source_id"]) if job.get("source") == "booking" else (None, None, None)
    if new == "working" and booking and body.get("arrival_code") and body["arrival_code"] != booking.get("arrival_code"):
        return 400, {"arrival_code": ["The code does not match the one in the customer's app."]}
    job["status"] = new
    job.setdefault("logs", []).append({"status": new, "note": body.get("note", ""), "created_at": now()})
    if new == "working":
        job["before_photos"] = body.get("photos", [])
        job["started_at"] = now()
    if new == "completed":
        job["after_photos"] = body.get("photos", [])
        job["completed_at"] = now()
        job["provider_note"] = body.get("note", "")
        me = lookup(user, "/api/providers/me/")
        if me:
            me["jobs_completed"] = me.get("jobs_completed", 0) + 1
            put(user, "/api/providers/me/", me)
    update_everywhere(lambda o: o.get("id") == job["id"] and o.get("source") == job.get("source"), lambda o: o.update(job), ["/api/providers/jobs/", "/api/admin/jobs/"])
    put(user, f"/api/providers/jobs/{job_id}/", job)
    if booking:
        track(booking["id"], new, body.get("note", ""))
        change = {"status": new}
        if new == "completed":
            change.update(completed_at=now(), warranty_until=str(date.today() + timedelta(days=booking.get("warranty_days") or 7)))
        update_everywhere(lambda o: o.get("id") == booking["id"] and "arrival_code" in o, lambda o: o.update(change), ["/api/orders/", "/api/admin/orders/"])
        if new == "completed":
            u, order, _ = find_booking(booking["id"])
            if order and all(b["status"] in ("completed", "cancelled") for b in order["bookings"]) and not order["items"]:
                update_everywhere(lambda o: o.get("id") == order["id"] and "bookings" in o, lambda o: o.update(status="completed"), ["/api/orders/", "/api/admin/orders/"])
    return 200, job


def accept_job(user, job_id):
    job = lookup(user, f"/api/providers/jobs/{job_id}/")
    if not job:
        return 404, {"detail": "Not found."}
    me = lookup(user, "/api/providers/me/") or {}
    claims = USERS[user]["tokens_claims"]
    job.update(status="accepted", provider=me.get("id"), provider_name=claims["name"], accepted_at=now())
    job.setdefault("logs", []).append({"status": "accepted", "note": "", "created_at": now()})
    _, order, booking = find_booking(job["source_id"]) if job.get("source") == "booking" else (None, None, None)
    if booking:
        job["customer_phone"] = order.get("contact_phone", "")
    # the job leaves every provider's "new jobs" list and joins this provider's own list
    edit("/api/providers/jobs/", lambda b, k: (b.update(results=[j for j in b["results"] if j["id"] != job["id"]], count=max(0, b.get("count", 1) - 1)) or b)
         if "tab=available" in k and isinstance(b, dict) else None)
    prepend("/api/providers/jobs/", job, [user], keep=lambda k: "tab=active" in k or "tab=" not in k)
    put(user, f"/api/providers/jobs/{job_id}/", job)
    if booking:
        track(booking["id"], "confirmed", claims["name"])
        update_everywhere(lambda o: o.get("id") == booking["id"] and "arrival_code" in o,
                          lambda o: o.update(status="confirmed", provider_name=claims["name"], provider_phone=claims["phone"], provider_id=claims["user_id"]),
                          ["/api/orders/", "/api/admin/orders/"])
        update_everywhere(lambda o: o.get("id") == order["id"] and "bookings" in o, lambda o: o.update(status="confirmed"), ["/api/orders/", "/api/admin/orders/"])
    return 200, job


def report_issue(user, body):
    claims = USERS.get(user, {}).get("tokens_claims", {})
    tpl = template(lambda o: "upvote_count" in o and "updates" in o)
    a = area(body.get("area_id") or 0)
    issue = fill(tpl, {
        "id": next_id(), "category": body.get("category", "other"), "title": body.get("title", ""), "description": body.get("description", ""),
        "photo_urls": body.get("photo_urls", []), "latitude": str(body.get("latitude")), "longitude": str(body.get("longitude")),
        "landmark": body.get("landmark", ""), "area_id": int(body.get("area_id") or 0), "area_name": body.get("area_name", a.get("name_bn", "")),
        "status": "reported", "authority_name": None, "upvote_count": 1, "upvoted": True, "distance_km": None,
        "reporter_name": claims.get("name", ""), "created_at": now(), "updated_at": now(), "resolved_at": None,
        "updates": [{"status": "reported", "note": "", "created_at": now()}]})
    UPVOTES.setdefault(issue["id"], set()).add(user)
    for u in known_users():
        put(u, f"/api/issues/{issue['id']}/", dict(issue, upvoted=(u == user)))

    def keep(k):
        q = dict(urllib.parse.parse_qsl(k.partition("?")[2]))
        if "status" in q and q["status"] and "reported" not in q["status"].split(","):
            return False
        if q.get("area") and int(q["area"]) != issue["area_id"]:
            return False
        if q.get("city") and q["city"] != a.get("city"):
            return False
        if q.get("category") and q["category"] != issue["category"]:
            return False
        return not q.get("mine")
    prepend("/api/issues/", issue, keep=keep)
    prepend("/api/issues/", issue, [user], keep=lambda k: "mine=1" in k)
    prepend("/api/admin/issues/", issue, ["01700000000"])
    return 201, issue


def upvote(user, issue_id):
    voters = UPVOTES.setdefault(int(issue_id), set())
    issue = lookup(user, f"/api/issues/{issue_id}/") or {}
    base = issue.get("upvote_count", 0) - (1 if user in voters else 0) - (1 if issue.get("upvoted") and user not in voters else 0)
    on = not (user in voters or issue.get("upvoted"))
    voters.discard(user)
    if on:
        voters.add(user)
    count = max(0, base + (1 if on else 0))
    update_everywhere(lambda o: o.get("id") == int(issue_id) and "upvote_count" in o, lambda o: o.update(upvote_count=count), ["/api/issues/", "/api/admin/issues/"])
    edit(f"/api/issues/{issue_id}/", lambda b, k: b.update(upvoted=on) or b, [user])
    return 200, {"upvoted": on, "upvote_count": count}


def admin_issue_status(issue_id, body):
    authorities = lookup("01700000000", "/api/admin/authorities/") or []
    auth = next((a for a in authorities if str(a["id"]) == str(body.get("authority"))), None)
    entry = {"status": body.get("status"), "note": (body.get("note", "") + (f" → {auth['name_bn']}" if auth else "")).strip(), "created_at": now()}

    def change(o):
        o["status"] = body.get("status")
        if auth:
            o["authority_name"] = {"bn": auth["name_bn"], "en": auth["name_en"]}
        if body.get("note"):
            o["admin_note"] = body["note"]
        if body.get("status") == "resolved":
            o["resolved_at"] = now()
            o["resolved_photo_urls"] = body.get("photos") or []
        if isinstance(o.get("updates"), list):
            o["updates"].append(entry)
    update_everywhere(lambda o: o.get("id") == int(issue_id) and "upvote_count" in o, change, ["/api/issues/", "/api/admin/issues/"])
    return 200, lookup("01700000000", f"/api/issues/{issue_id}/") or {}


def new_post(user, body):
    claims = USERS.get(user, {}).get("tokens_claims", {})
    tpl = template(lambda o: "like_count" in o and "comment_count" in o)
    a = area(body.get("area_id") or 0)
    post = fill(tpl, {"id": next_id(), "user_id": claims.get("user_id"), "author_name": claims.get("name", ""), "area_id": int(body.get("area_id") or 0),
                      "area_name": body.get("area_name", ""), "kind": body.get("kind", "tip"), "body": body.get("body", ""),
                      "photo_urls": body.get("photo_urls", []), "provider_name": body.get("provider_name", ""), "like_count": 0,
                      "comment_count": 0, "liked": False, "mine": True, "created_at": now()})

    def keep(k):
        q = dict(urllib.parse.parse_qsl(k.partition("?")[2]))
        return (not q.get("area") or int(q["area"]) == post["area_id"]) and (not q.get("city") or q["city"] == a.get("city")) \
            and (not q.get("kind") or q["kind"] == post["kind"])
    prepend("/api/community/posts/", post, keep=keep)
    return 201, post


def custom_request(user, body):
    claims = USERS.get(user, {}).get("tokens_claims", {})
    tpl = template(lambda o: "service_type" in o and "budget_min" in o)
    req = fill(tpl, {"id": next_id(), "service_type": body.get("service_type", ""), "description": body.get("description", ""),
                     "media_urls": body.get("media_urls", []), "area_id": int(body.get("area_id") or 0), "area_name": body.get("area_name", ""),
                     "address_line": body.get("address_line", ""), "preferred_date": body.get("preferred_date"), "budget_min": body.get("budget_min"),
                     "budget_max": body.get("budget_max"), "status": "submitted", "quote": None, "quotes": [], "created_at": now(), "updated_at": now(),
                     "user_id": claims.get("user_id"), "customer_name": claims.get("name", ""), "customer_phone": claims.get("phone", ""),
                     "logs": [{"status": "submitted", "note": "", "created_at": now()}]})
    put(user, f"/api/custom-requests/{req['id']}/", req)
    prepend("/api/custom-requests/", req, [user])
    put("01700000000", f"/api/admin/custom-requests/{req['id']}/", req)
    prepend("/api/admin/custom-requests/", req, ["01700000000"], keep=lambda k: "status=" not in k or "submitted" in k or k.endswith("status="))
    return 201, req


def quote_request(req_id, body):
    labor, materials, transport, fee = (float(body.get(k) or 0) for k in ("labor", "materials", "transport", "platform_fee"))
    quote = {"id": next_id(), "labor": money(labor), "materials": money(materials), "transport": money(transport), "platform_fee": money(fee),
             "total": money(labor + materials + transport + fee), "days_needed": body.get("days_needed", 1), "note": body.get("note", ""),
             "valid_until": str(date.today() + timedelta(days=7)), "created_at": now()}
    update_everywhere(lambda o: o.get("id") == int(req_id) and "service_type" in o,
                      lambda o: o.update(status="quote_sent", quote=quote, quotes=(o.get("quotes") or []) + [quote]),
                      ["/api/custom-requests/", "/api/admin/custom-requests/"])
    return 200, lookup("01700000000", f"/api/admin/custom-requests/{req_id}/") or {}


def subscribe(user, body):
    claims = USERS.get(user, {}).get("tokens_claims", {})
    tpl = template(lambda o: "plan_detail" in o or ("visits" in o and "preferred_weekday" in o))
    plan = lookup("guest", f"/api/subscription-plans/{body.get('plan')}/") or {}
    quote = lookup(user, f"/api/subscriptions/quote/?plan={body.get('plan')}") or {}
    start = date.fromisoformat(body.get("start_date") or str(date.today() + timedelta(days=1)))
    days = int(body.get("duration_days") or 30)
    price = quote.get("total") or quote.get("price") or "0.00"
    sub = fill(tpl, {"id": next_id(), "user_id": claims.get("user_id"), "customer_name": claims.get("name", ""), "plan": body.get("plan"),
                     "plan_detail": plan, "duration_days": days, "home_size": body.get("home_size", 0), "start_date": str(start),
                     "end_date": str(start + timedelta(days=days - 1)), "slot": body.get("slot", "09-11"), "area_id": body.get("area_id"),
                     "area_name": body.get("area_name", ""), "address_line": body.get("address_line", ""), "price": price, "amount_due": price,
                     "payment_method": body.get("payment_method", "cod"), "status": "active" if body.get("payment_method", "cod") == "cod" else "pending_payment",
                     "auto_renew": body.get("auto_renew", True), "visits": [], "created_at": now()})
    put(user, f"/api/subscriptions/{sub['id']}/", sub)
    prepend("/api/subscriptions/", sub, [user])
    prepend("/api/admin/subscriptions/", sub, ["01700000000"])
    return 201, sub


def save_upload(handler):
    UPLOADS.mkdir(exist_ok=True)
    ctype = handler.headers.get("Content-Type", "")
    data = handler.rfile.read(int(handler.headers.get("Content-Length", 0)))
    msg = email.parser.BytesParser(policy=email.policy.default).parsebytes(b"Content-Type: " + ctype.encode() + b"\r\n\r\n" + data)
    for part in msg.iter_parts():
        if part.get_filename():
            ext = pathlib.Path(part.get_filename()).suffix.lower() or ".jpg"
            name = f"{next_id()}{ext}"
            (UPLOADS / name).write_bytes(part.get_payload(decode=True))
            return 201, {"id": next_id(), "url": f"/media/public/uploads/{name}"}
    return 400, {"file": ["No file."]}


def payment_page(tran):
    p = PAYMENTS.get(tran)
    if not p:
        return None
    hidden = f'<input type="hidden" name="tran_id" value="{tran}">'
    title = {"bkash": "বিকাশ পেমেন্ট", "nagad": "নগদ পেমেন্ট"}.get(p["gateway"], "অনলাইন পেমেন্ট (ডেমো)")
    pay = {"bkash": "বিকাশ দিয়ে নিশ্চিত করুন", "nagad": "নগদ দিয়ে পেমেন্ট করুন"}.get(p["gateway"], "Pay")
    return f"""<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>{title}</title>
<body style="font-family:system-ui,'Noto Sans Bengali',sans-serif;background:#f6f7f6;display:grid;place-items:center;min-height:100vh;margin:0">
<div style="background:#fff;border:2px solid #136b3f;border-radius:16px;padding:24px;width:340px">
<h2 style="margin:0 0 8px">{title}</h2><p style="font-size:28px;font-weight:700;margin:0 0 6px">৳ {p['amount']}</p>
<p style="color:#666;font-size:13px">ট্রানজ্যাকশন আইডি: {tran} · ডেমো পেমেন্ট, টাকা কাটা হবে না</p>
<form method="post" action="/api/payments/gateway/success/">{hidden}<button class="pay" type="submit" style="width:100%;padding:12px;border:0;border-radius:10px;background:#136b3f;color:#fff;font-size:16px">{pay}</button></form>
<form method="post" action="/api/payments/gateway/cancel/" style="margin-top:8px">{hidden}<button type="submit" style="width:100%;padding:12px;border:0;border-radius:10px;background:#eee;font-size:16px">বাতিল করুন</button></form>
</div></body>"""


# ---------------------------------------------------------------- HTTP

class Handler(http.server.BaseHTTPRequestHandler):
    server_version = "ShohorSathiStandalone/1.0"

    def log_message(self, fmt, *args):
        if "/api/" in self.path and not self.path.startswith("/api/notifications/unread"):
            sys.stderr.write(f"{self.command} {self.path.split('?')[0]} {args[1] if len(args) > 1 else ''}\n")

    # -- plumbing
    def cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, PATCH, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")

    def send(self, status, data=None, ctype="application/json; charset=utf-8", headers=None):
        body = b"" if data is None else data if isinstance(data, bytes) else json.dumps(data, ensure_ascii=False).encode()
        self.send_response(status)
        if status != 204:
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
        for k, v in (headers or {}).items():
            self.send_header(k, v)
        self.cors()
        self.end_headers()
        if status != 204:
            self.wfile.write(body)

    def body(self):
        n = int(self.headers.get("Content-Length", 0) or 0)
        if not n:
            return {}
        raw_body = self.rfile.read(n).decode("utf-8", "replace")
        if "application/x-www-form-urlencoded" in self.headers.get("Content-Type", ""):
            return dict(urllib.parse.parse_qsl(raw_body))
        try:
            return json.loads(raw_body)
        except ValueError:
            return {}

    def user(self):
        auth = self.headers.get("Authorization", "")
        claims = read_token(auth[7:]) if auth.startswith("Bearer ") else None
        return claims.get("phone") if claims and claims.get("phone") in USERS else "guest"

    def do_OPTIONS(self):
        self.send(204)

    # -- reads
    def do_GET(self):
        url = urllib.parse.urlparse(self.path)
        path = url.path
        if path.startswith("/media/"):
            return self.media(path)
        if path in ("/", "/health"):
            return self.send(200, {"status": "ok", "mode": "standalone"})
        m = re.match(r"^/api/payments/(?:bkash/|nagad/)?mock/([^/]+)/$", path)
        if m:
            page = payment_page(m.group(1))
            return self.send(200, page.encode(), "text/html; charset=utf-8") if page else self.send(404, {"detail": "Not found."})
        user = self.user()
        with LOCK:
            if path == "/api/cart/":
                return self.send(200, cart_body(user))
            if path == "/api/notifications/unread-count/":
                notes = items_of(lookup(user, "/api/notifications/")) or []
                return self.send(200, {"unread": sum(1 for n in notes if not n.get("read_at"))})
            if path == "/api/me/" and user != "guest" and lookup(user, "/api/me/") is None:
                c = USERS[user]["tokens_claims"]
                return self.send(200, {"id": c["user_id"], "phone": c["phone"], "full_name": c["name"], "role": c["role"], "email": ""})
            m = re.match(r"^/api/bookings/(\d+)/$", path)
            if m:
                _, _, booking = find_booking(m.group(1))
                return self.send(200, booking) if booking else self.send(404, {"detail": "Not found."})
            m = re.match(r"^/api/providers/share/([^/]+)/$", path)
            if m:
                share = SHARES.get(m.group(1))
                if not share or share["expires"] < time.time():
                    return self.send(404, {"detail": "This link has expired."})
                _, _, booking = find_booking(share["source_id"])
                return self.send(200, {"title": booking["service_name"], "status": booking["status"], "scheduled_date": booking["scheduled_date"],
                                       "slot": booking["slot"], "provider_first_name": (booking.get("provider_name") or "").split(" ")[0],
                                       "provider_verified": bool(booking.get("provider_name")), "location": None,
                                       "expires_at": datetime.fromtimestamp(share["expires"]).astimezone().isoformat()})
            m = re.match(r"^/api/community/posts/(\d+)/comments/$", path)
            if m:
                return self.send(200, COMMENTS.get(int(m.group(1)), lookup(user, path) or []))
            if path == "/api/providers/reviews/":
                q = dict(urllib.parse.parse_qsl(url.query))
                mine = COMMENTS.get(("review", user, q.get("source"), q.get("source_id")))
                if mine or q.get("source_id"):
                    return self.send(200, mine or raw(user, route_key(path, url.query)))
            body = lookup(user, route_key(path, url.query))
        if body is None:
            last = path.rstrip("/").split("/")[-1]
            if last.isdigit() or last not in SEGMENTS:
                return self.send(404, {"detail": "Not found."})
            return self.send(200, {"count": 0, "next": None, "previous": None, "results": []})
        return self.send(200, body)

    def media(self, path):
        rel = urllib.parse.unquote(path)
        candidates = []
        if rel.startswith("/media/public/uploads/"):
            candidates.append(UPLOADS / rel.rsplit("/", 1)[1])
        if rel.startswith("/media/public/demo/"):
            candidates.append(ROOT / "demo" / "images" / rel[len("/media/public/demo/"):])
        for c in candidates:
            if c.is_file():
                return self.send(200, c.read_bytes(), mimetypes.guess_type(str(c))[0] or "application/octet-stream",
                                 {"Cache-Control": "max-age=86400"})
        return self.send(404, {"detail": "Not found."})

    # -- writes
    def do_POST(self):
        self.write("POST")

    def do_PATCH(self):
        self.write("PATCH")

    def do_PUT(self):
        self.write("PUT")

    def do_DELETE(self):
        self.write("DELETE")

    def write(self, method):
        path = urllib.parse.urlparse(self.path).path
        if path == "/api/media/" and method == "POST":
            with LOCK:
                return self.send(*save_upload(self))
        body = self.body()
        if path == "/api/payments/gateway/success/" or path == "/api/payments/gateway/cancel/" or path == "/api/payments/gateway/fail/":
            return self.gateway_return(path, body)
        with LOCK:
            status, data = self.route(method, path, body, self.user())
        if status in (301, 302):
            return self.send(status, b"", "text/plain", {"Location": data})
        return self.send(status, None if status == 204 else data)

    def gateway_return(self, path, body):
        with LOCK:
            p = PAYMENTS.get(body.get("tran_id", ""))
            if not p:
                return self.send(404, {"detail": "Unknown payment."})
            ok = path.endswith("/success/")
            if ok and p["purpose"] == "order":
                update_everywhere(lambda o: o.get("id") == p["reference_id"] and "bookings" in o, lambda o: o.update(payment_status="paid", status="confirmed"),
                                  ["/api/orders/", "/api/admin/orders/"])
            if ok and p["purpose"] == "subscription":
                update_everywhere(lambda o: o.get("id") == p["reference_id"] and "duration_days" in o, lambda o: o.update(status="active", paid=True),
                                  ["/api/subscriptions/", "/api/admin/subscriptions/"])
            q = urllib.parse.urlencode({"tran_id": body["tran_id"], "status": "held" if ok else "cancelled", "purpose": p["purpose"], "reference_id": p["reference_id"]})
        return self.send(302, b"", "text/plain", {"Location": f"{CUSTOMER_WEB}/payment/result?{q}"})

    def route(self, method, path, b, user):
        # ---- auth
        if path == "/api/auth/login/":
            phone = str(b.get("phone", ""))
            if phone in USERS and b.get("password") == PASSWORD:
                return 200, tokens_for(phone)
            return 401, {"detail": "No active account found with the given credentials"}
        if path == "/api/auth/token/refresh/":
            claims = read_token(b.get("refresh", "")) or {}
            phone = claims.get("phone")
            return (200, tokens_for(phone)) if phone in USERS else (401, {"detail": "Token is invalid or expired", "code": "token_not_valid"})
        if path == "/api/auth/otp/request/":
            print(f"OTP for {b.get('phone')}: {DEMO_OTP}", flush=True)
            return 200, {"detail": "OTP sent.", "dev_hint": f"demo OTP {DEMO_OTP}"}
        if path == "/api/auth/register/":
            phone = str(b.get("phone", ""))
            if b.get("otp") != DEMO_OTP:
                return 400, {"otp": ["Wrong code. In this demo the code is 123456."]}
            if phone in USERS:
                return 400, {"phone": ["This number is already registered."]}
            USERS[phone] = {"tokens_claims": {"user_id": next_id(), "role": "customer", "name": b.get("full_name", ""), "phone": phone}, "me": None}
            return 201, tokens_for(phone)
        if user == "guest":
            return 401, {"detail": "Authentication credentials were not provided."}

        # ---- customer
        if path == "/api/cart/items/" and method == "POST":
            kind, slug = b.get("item_type", "service"), b.get("slug", "")
            item = catalog(kind, slug)
            if not item:
                return 400, {"slug": ["This item is not available."]}
            price = float(item.get("price") or item.get("base_price") or 0)
            cart = CARTS.setdefault(user, [])
            same = next((c for c in cart if c["slug"] == slug and c["item_type"] == kind), None)
            qty = 1 if kind == "service" else int(b.get("quantity") or 1)
            if same:
                same["quantity"] = 1 if kind == "service" else same["quantity"] + qty
                same["line_total"] = money(price * same["quantity"])
                return 201, same
            row = {"id": next_id(), "item_type": kind, "slug": slug, "name": item.get("name_bn", slug), "unit_price": money(price), "quantity": qty,
                   "line_total": money(price * qty)}
            cart.append(row)
            return 201, row
        m = re.match(r"^/api/cart/items/(\d+)/$", path)
        if m:
            cart = CARTS.setdefault(user, [])
            row = next((c for c in cart if c["id"] == int(m.group(1))), None)
            if not row:
                return 404, {"detail": "Not found."}
            if method == "DELETE":
                cart.remove(row)
                return 204, None
            row["quantity"] = max(1, int(b.get("quantity") or row["quantity"]))
            row["line_total"] = money(float(row["unit_price"]) * row["quantity"])
            return 200, row
        if path == "/api/orders/" and method == "POST":
            return place_order(user, b)
        if path == "/api/me/addresses/" and method == "POST":
            a = area(b.get("area") or 0)
            addr = {"id": next_id(), "label": b.get("label") or "বাসা", "area": a["id"], "area_detail": a, "line": b.get("line", ""),
                    "latitude": b.get("latitude"), "longitude": b.get("longitude"), "is_default": bool(b.get("is_default"))}
            current = lookup(user, "/api/me/addresses/") or []
            put(user, "/api/me/addresses/", (current if isinstance(current, list) else []) + [addr])
            return 201, addr
        m = re.match(r"^/api/orders/(\d+)/cancel/$", path)
        if m:
            oid = int(m.group(1))
            update_everywhere(lambda o: o.get("id") == oid and "bookings" in o,
                              lambda o: (o.update(status="cancelled"), [bk.update(status="cancelled") for bk in o["bookings"]]),
                              ["/api/orders/", "/api/admin/orders/"])
            return 200, lookup(user, f"/api/orders/{oid}/")
        m = re.match(r"^/api/bookings/(\d+)/(reschedule|cancel)/$", path)
        if m:
            bid = int(m.group(1))
            change = {"status": "cancelled"} if m.group(2) == "cancel" else {"scheduled_date": b.get("scheduled_date"), "slot": b.get("slot") or "09-11"}
            update_everywhere(lambda o: o.get("id") == bid and "arrival_code" in o, lambda o: o.update(change), ["/api/orders/", "/api/admin/orders/"])
            _, _, booking = find_booking(bid)
            return 200, booking or {}
        if path == "/api/providers/reviews/" and method == "POST":
            review = {"id": next_id(), "rating": int(b.get("rating") or 5), "comment": b.get("comment", ""), "created_at": now()}
            COMMENTS[("review", user, str(b.get("source")), str(b.get("source_id")))] = review
            return 201, review
        if path == "/api/payments/initiate/":
            tran = f"SS{next_id():X}DEMO"
            amount = "0.00"
            if b.get("purpose") == "order":
                order = lookup(user, f"/api/orders/{b.get('reference_id')}/") or {}
                amount = order.get("total", "0.00")
            elif b.get("purpose") == "subscription":
                sub = lookup(user, f"/api/subscriptions/{b.get('reference_id')}/") or {}
                amount = sub.get("amount_due") or sub.get("price") or "0.00"
            gateway = b.get("gateway") or "sslcommerz"
            PAYMENTS[tran] = {"purpose": b.get("purpose"), "reference_id": int(b.get("reference_id") or 0), "gateway": gateway, "amount": amount, "user": user}
            prefix = {"bkash": "bkash/", "nagad": "nagad/"}.get(gateway, "")
            return 201, {"tran_id": tran, "amount": amount, "gateway": gateway, "redirect_url": f"http://localhost:{PORT}/api/payments/{prefix}mock/{tran}/"}
        if path == "/api/providers/share/" and method == "POST":
            token = f"{next_id():x}{random.randint(10**8, 10**9):x}"
            SHARES[token] = {"source_id": int(b.get("source_id") or 0), "expires": time.time() + 86400}
            return 201, {"token": token}
        if path == "/api/issues/" and method == "POST":
            return report_issue(user, b)
        m = re.match(r"^/api/issues/(\d+)/upvote/$", path)
        if m:
            return upvote(user, m.group(1))
        if path == "/api/community/posts/" and method == "POST":
            return new_post(user, b)
        m = re.match(r"^/api/community/posts/(\d+)/(like|comments)/$", path)
        if m:
            pid = int(m.group(1))
            if m.group(2) == "like":
                liked = LIKES.setdefault(pid, set())
                on = user not in liked
                (liked.add if on else liked.discard)(user)
                update_everywhere(lambda o: o.get("id") == pid and "like_count" in o,
                                  lambda o: o.update(like_count=max(0, o["like_count"] + (1 if on else -1))), ["/api/community/posts/"])
                post = lookup(user, "/api/community/posts/") or {}
                count = next((p["like_count"] for p in items_of(post) or [] if p["id"] == pid), 0)
                return 200, {"liked": on, "like_count": count}
            claims = USERS[user]["tokens_claims"]
            comment = {"id": next_id(), "author_name": claims["name"], "body": b.get("body", ""), "created_at": now()}
            COMMENTS.setdefault(pid, []).append(comment)
            update_everywhere(lambda o: o.get("id") == pid and "comment_count" in o, lambda o: o.update(comment_count=o["comment_count"] + 1),
                              ["/api/community/posts/"])
            return 201, comment
        if path == "/api/custom-requests/ai-quote/":
            return 201, ai_quote(user, b)
        if path == "/api/custom-requests/" and method == "POST":
            return custom_request(user, b)
        m = re.match(r"^/api/custom-requests/(\d+)/(accept|reject|counter|cancel)/$", path)
        if m:
            rid, act = int(m.group(1)), m.group(2)
            status = {"accept": "accepted", "reject": "rejected", "counter": "countered", "cancel": "cancelled"}[act]
            update_everywhere(lambda o: o.get("id") == rid and "service_type" in o, lambda o: o.update(status=status),
                              ["/api/custom-requests/", "/api/admin/custom-requests/"])
            return 200, lookup(user, f"/api/custom-requests/{rid}/") or {}
        if path == "/api/subscriptions/" and method == "POST":
            return subscribe(user, b)
        m = re.match(r"^/api/subscriptions/(\d+)/(cancel|pause|resume)/$", path)
        if m:
            sid = int(m.group(1))
            status = {"cancel": "cancelled", "pause": "paused", "resume": "active"}[m.group(2)]
            update_everywhere(lambda o: o.get("id") == sid and "duration_days" in o, lambda o: o.update(status=status), ["/api/subscriptions/"])
            return 200, lookup(user, f"/api/subscriptions/{sid}/") or {}
        m = re.match(r"^/api/home-profiles/(\d+)/(add-reminder|complete-reminder/(\d+))/$", path)
        if m:
            hid = int(m.group(1))
            homes = lookup(user, "/api/home-profiles/")
            for h in items_of(homes) or []:
                if h["id"] != hid:
                    continue
                if m.group(3):
                    for r in h["reminders"]:
                        if r["id"] == int(m.group(3)):
                            r.update(is_completed=True, last_serviced_date=str(date.today()))
                            result = r
                else:
                    tpl = h["reminders"][0] if h["reminders"] else {}
                    result = fill(tpl, {"id": next_id(), "home": hid, "title_bn": b.get("title_bn", ""), "title_en": b.get("title_en", ""),
                                        "due_date": b.get("due_date"), "recommended_service_slug": b.get("recommended_service_slug", ""),
                                        "frequency_days": b.get("frequency_days", 180), "is_completed": False, "created_at": now()})
                    h["reminders"].append(result)
                put(user, "/api/home-profiles/", homes)
                return (200 if m.group(3) else 201), result
            return 404, {"detail": "Not found."}
        if path == "/api/notifications/read-all/":
            edit("/api/notifications/", lambda bd, k: ([n.update(read_at=n.get("read_at") or now()) for n in items_of(bd) or []], bd)[1], [user])
            return 200, {"detail": "ok"}
        m = re.match(r"^/api/notifications/(\d+)/read/$", path)
        if m:
            nid = int(m.group(1))
            edit("/api/notifications/", lambda bd, k: ([n.update(read_at=now()) for n in items_of(bd) or [] if n["id"] == nid], bd)[1], [user])
            return 200, {"detail": "ok"}

        # ---- provider
        m = re.match(r"^/api/providers/jobs/(\d+)/(accept|reject)/$", path)
        if m:
            if m.group(2) == "accept":
                return accept_job(user, m.group(1))
            return 200, lookup(user, f"/api/providers/jobs/{m.group(1)}/") or {}
        m = re.match(r"^/api/providers/jobs/(\d+)/status/$", path)
        if m:
            return job_status(user, m.group(1), b)
        m = re.match(r"^/api/providers/jobs/(\d+)/rate-customer/$", path)
        if m:
            jid = int(m.group(1))
            update_everywhere(lambda o: o.get("id") == jid and "customer_rating" in o,
                              lambda o: o.update(customer_rating=int(b.get("rating") or 5), customer_feedback=b.get("feedback", "")), ["/api/providers/jobs/"])
            return 200, lookup(user, f"/api/providers/jobs/{jid}/") or {}

        # ---- admin
        m = re.match(r"^/api/admin/loyalty/accounts/(\d+)/adjust/$", path)
        if m:
            owner = next((u for u in known_users() if (raw(u, "/api/loyalty/me/") or {}).get("user_id") == int(m.group(1))), None)
            if not owner:
                return 404, {"detail": "Not found."}
            acc = lookup(owner, "/api/loyalty/me/")
            acc["points"] = max(0, acc["points"] + int(b.get("points") or 0))
            acc["points_value"] = str(acc["points"])
            acc["history"].insert(0, {"kind": "points", "delta": money(b.get("points") or 0), "reason": b.get("reason", "admin"), "ref": "", "created_at": now()})
            put(owner, "/api/loyalty/me/", acc)
            return 200, acc
        m = re.match(r"^/api/admin/issues/(\d+)/status/$", path)
        if m:
            return admin_issue_status(m.group(1), b)
        m = re.match(r"^/api/admin/custom-requests/(\d+)/quote/$", path)
        if m:
            return quote_request(m.group(1), b)
        m = re.match(r"^/api/admin/custom-requests/(\d+)/review/$", path)
        if m:
            rid = int(m.group(1))
            update_everywhere(lambda o: o.get("id") == rid and "service_type" in o, lambda o: o.update(status="under_review"),
                              ["/api/custom-requests/", "/api/admin/custom-requests/"])
            return 200, lookup(user, f"/api/admin/custom-requests/{rid}/") or {}

        # ---- anything else: accept the change and echo it back
        return self.generic(method, path, b, user)

    def generic(self, method, path, b, user):
        if method == "DELETE":
            return 204, None
        detail_path = path
        parts = path.rstrip("/").split("/")
        if not parts[-1].isdigit() and len(parts) > 2 and parts[-2].isdigit():
            detail_path = "/".join(parts[:-1]) + "/"   # /x/<id>/<action>/ acts on /x/<id>/
        existing = lookup(user, detail_path) if parts[-1].isdigit() or detail_path != path else None
        if isinstance(existing, dict):
            existing.update({k: v for k, v in b.items() if k in existing})
            put(user, detail_path, existing)
            return 200, existing
        if method == "POST":
            return 201, {"id": next_id(), **b, "created_at": now()}
        current = lookup(user, path)
        if isinstance(current, dict):
            current.update(b)
            put(user, path, current)
            return 200, current
        return 200, b


class Server(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True
    allow_reuse_address = True


if __name__ == "__main__":
    n_users = len([u for u in USERS])
    print(f"ShohorSathi standalone backend on http://localhost:{PORT}  ({n_users} demo accounts, recorded {SNAP.get('recorded_at', '?')[:10]})")
    print("Start the apps in another terminal with: pnpm dev   →  http://localhost:5173 · :5174 · :5175   (password demo1234)")
    try:
        Server(("0.0.0.0", PORT), Handler).serve_forever()
    except OSError as e:
        sys.exit(f"Port {PORT} is busy ({e}). Stop the Docker stack (docker compose stop gateway) or pass another port.")
    except KeyboardInterrupt:
        pass
