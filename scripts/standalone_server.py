"""ShohorSathi Standalone Zero-Docker Demo API Server.
Enables running the entire ShohorSathi platform on ANY laptop (Windows, Mac, Linux)
without Docker, PostgreSQL, Redis, or Celery.

Usage:
    python scripts/standalone_server.py [8088]

Requirements:
    Python 3.8+ (Standard Library only - NO PIP PACKAGES NEEDED!)
"""
import base64
import copy
import hashlib
import hmac
import http.server
import json
import mimetypes
import os
import pathlib
import sys
import time
import urllib.parse
from datetime import datetime, timedelta

ROOT = pathlib.Path(__file__).resolve().parent.parent
DB_FILE = ROOT / "demo" / "data" / "standalone_db.json"
PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8088

# Load initial database snapshot
if DB_FILE.exists():
    with open(DB_FILE, "r", encoding="utf-8") as f:
        DB = json.load(f)
else:
    DB = {}

# In-memory runtime state
CARTS = {}  # user_id -> items
USER_SESSIONS = {}
CUSTOM_REQUESTS = []

DEMO_USERS = {
    "01700000000": {"id": 1, "phone": "01700000000", "full_name": "শহরসাথী অ্যাডমিন", "role": "admin", "is_verified": True},
    "01711000001": {"id": 101, "phone": "01711000001", "full_name": "রহিম উদ্দিন", "role": "customer", "is_verified": True},
    "01711000002": {"id": 102, "phone": "01711000002", "full_name": "নুসরাত জাহান", "role": "customer", "is_verified": True},
    "01711000004": {"id": 104, "phone": "01711000004", "full_name": "ফারহানা ইসলাম", "role": "customer", "is_verified": True},
    "01811000001": {"id": 201, "phone": "01811000001", "full_name": "করিম মিয়া", "role": "provider", "is_verified": True},
    "01811000002": {"id": 202, "phone": "01811000002", "full_name": "সালমা বেগম", "role": "provider", "is_verified": True},
    "01811000006": {"id": 206, "phone": "01811000006", "full_name": "সাইফুল ইসলাম", "role": "provider", "is_verified": True},
}


def make_jwt(payload):
    header = base64.urlsafe_b64encode(json.dumps({"alg": "HS256", "typ": "JWT"}).encode()).decode().rstrip("=")
    exp = int(time.time()) + 86400 * 14
    body = {**payload, "exp": exp, "orig_iat": int(time.time())}
    payload_b64 = base64.urlsafe_b64encode(json.dumps(body).encode()).decode().rstrip("=")
    sig = hmac.new(b"shohorsathi-secret", f"{header}.{payload_b64}".encode(), hashlib.sha256).digest()
    sig_b64 = base64.urlsafe_b64encode(sig).decode().rstrip("=")
    return f"{header}.{payload_b64}.{sig_b64}"


def parse_jwt(token):
    try:
        parts = token.split(".")
        if len(parts) != 3:
            return None
        padded = parts[1] + "=" * ((4 - len(parts[1]) % 4) % 4)
        return json.loads(base64.urlsafe_b64decode(padded).decode())
    except Exception:
        return None


class StandaloneHandler(http.server.BaseHTTPRequestHandler):
    def send_cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, PATCH, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization, X-Requested-With")

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_cors()
        self.end_headers()

    def reply_json(self, data, status=200):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_cors()
        self.end_headers()
        self.wfile.write(body)

    def read_body(self):
        clen = int(self.headers.get("Content-Length", 0))
        if clen == 0:
            return {}
        raw = self.rfile.read(clen).decode("utf-8")
        try:
            return json.loads(raw)
        except Exception:
            return {}

    def get_user(self):
        auth = self.headers.get("Authorization", "")
        if auth.startswith("Bearer "):
            payload = parse_jwt(auth[7:])
            if payload:
                user_id = payload.get("user_id")
                phone = payload.get("phone", "")
                return DEMO_USERS.get(phone) or {
                    "id": user_id or 101,
                    "phone": phone or "01711000001",
                    "full_name": payload.get("full_name", "ব্যবহারকারী"),
                    "role": payload.get("role", "customer"),
                }
        return None

    def serve_file(self, file_path):
        if not file_path.exists() or not file_path.is_file():
            self.send_response(404)
            self.end_headers()
            return
        mime, _ = mimetypes.guess_type(str(file_path))
        data = file_path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", mime or "application/octet-stream")
        self.send_header("Content-Length", str(len(data)))
        self.send_cors()
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        qs = urllib.parse.parse_qs(parsed.query)

        # 1. Media Files (Static Images)
        if path.startswith("/media/") or path.startswith("/images/"):
            rel = path.replace("/media/public/demo/", "").replace("/media/", "").replace("/images/", "")
            candidates = [
                ROOT / "apps" / "customer-web" / "public" / "images" / rel,
                ROOT / "demo" / "images" / rel,
                ROOT / "apps" / "customer-web" / "public" / path.lstrip("/"),
            ]
            for c in candidates:
                if c.exists():
                    return self.serve_file(c)
            # Default placeholder image if missing
            sample = ROOT / "apps" / "customer-web" / "public" / "images" / "categories" / "ac-repair.jpg"
            if sample.exists():
                return self.serve_file(sample)
            self.send_response(404)
            self.end_headers()
            return

        # 2. Categories
        if path == "/api/categories/":
            cats = DB.get("categories", [])
            kind = qs.get("kind", [None])[0]
            if kind:
                cats = [c for c in cats if c.get("kind") == kind]
            return self.reply_json(cats)

        # 3. Services Catalog
        if path == "/api/services/":
            srvs = copy.deepcopy(DB.get("services", []))
            q = qs.get("q", [""])[0].lower()
            cat = qs.get("category", [""])[0]
            emergency = qs.get("emergency", [""])[0]
            if cat:
                srvs = [s for s in srvs if s.get("category_slug") == cat or str(s.get("category")) == cat]
            if emergency == "1":
                srvs = [s for s in srvs if s.get("emergency_available")]
            if q:
                srvs = [s for s in srvs if q in s.get("name_bn", "").lower() or q in s.get("name_en", "").lower() or q in s.get("description", "").lower()]
            return self.reply_json({"count": len(srvs), "next": None, "previous": None, "results": srvs})

        if path.startswith("/api/services/") and not path.endswith("/sponsor/"):
            slug = path.strip("/").split("/")[-1]
            srvs = DB.get("services", [])
            match = next((s for s in srvs if s.get("slug") == slug), None)
            if match:
                return self.reply_json(match)
            return self.reply_json(srvs[0] if srvs else {}, 200)

        # 4. Products Shop
        if path == "/api/products/":
            prods = DB.get("products", [])
            cat = qs.get("category", [""])[0]
            if cat:
                prods = [p for p in prods if p.get("category_slug") == cat]
            return self.reply_json({"count": len(prods), "next": None, "previous": None, "results": prods})

        # 5. Areas (Dhaka, Khulna, Chattogram)
        if path == "/api/areas/":
            return self.reply_json(DB.get("areas", []))

        # 6. Group Deals
        if path == "/api/group-deals/":
            deals = DB.get("group_deals", [])
            return self.reply_json({"count": len(deals), "next": None, "previous": None, "results": deals})

        # 7. Seasonal Packages
        if path == "/api/seasonal-packages/":
            pkgs = DB.get("seasonal_packages", [])
            return self.reply_json({"count": len(pkgs), "next": None, "previous": None, "results": pkgs})

        # 8. Subscription Plans
        if path == "/api/subscription-plans/":
            return self.reply_json(DB.get("subscription_plans", []))

        # 9. City Issues & Transparency
        if path == "/api/issues/":
            issues = DB.get("issues", [])
            return self.reply_json({"count": len(issues), "next": None, "previous": None, "results": issues})

        if path == "/api/issues/transparency/":
            return self.reply_json(DB.get("transparency", {}))

        if path == "/api/admin/authorities/":
            return self.reply_json(DB.get("authorities", []))

        # 10. Community Posts
        if path == "/api/community/posts/":
            posts = DB.get("community_posts", [])
            return self.reply_json({"count": len(posts), "next": None, "previous": None, "results": posts})

        # 11. Customer Home Profile
        if path == "/api/home-profiles/":
            return self.reply_json(DB.get("home_profiles", []))

        # 12. Cart
        if path == "/api/cart/":
            user = self.get_user()
            uid = user["id"] if user else 101
            items = CARTS.get(uid, [])
            total = sum(float(i.get("unit_price", 0)) * i.get("quantity", 1) for i in items)
            return self.reply_json({"items": items, "total": f"{total:.2f}"})

        # 13. Customer Orders
        if path == "/api/orders/":
            orders = DB.get("customer_orders", [])
            return self.reply_json({"count": len(orders), "next": None, "previous": None, "results": orders})

        if path.startswith("/api/orders/") and path.endswith("/rent-receipt/"):
            oid = path.strip("/").split("/")[2]
            return self.reply_json({
                "order_id": int(oid) if oid.isdigit() else 1,
                "receipt_number": f"RDR-2026-{oid}",
                "approval_status": "approved",
                "approved_at": datetime.now().isoformat(),
                "landlord_phone": "01811000000",
                "amount": "800.00",
                "certification_bn": "বাড়িভাড়া থেকে কর্তনযোগ্য ভাউচার (ShohorSathi Certified)",
            })

        if path.startswith("/api/orders/") and len(path.strip("/").split("/")) == 3:
            oid = path.strip("/").split("/")[2]
            orders = DB.get("customer_orders", [])
            order = next((o for o in orders if str(o.get("id")) == str(oid)), None)
            if not order and orders:
                order = orders[0]
            return self.reply_json(order or {})

        # 14. Provider Portal
        if path == "/api/providers/me/":
            return self.reply_json(DB.get("provider_me", {
                "id": 1, "phone": "01811000001", "name": "করিম মিয়া", "is_online": True,
                "rating": "4.9", "service_type": "electrician", "completed_jobs": 48
            }))

        if path == "/api/providers/earnings/":
            return self.reply_json(DB.get("provider_earnings", {
                "balance": "8450.00", "today_earnings": "1200.00", "week_earnings": "6800.00", "instant_payout_eligible": True
            }))

        if path.startswith("/api/providers/jobs/"):
            tab = qs.get("tab", ["available"])[0]
            if tab == "available":
                jobs = DB.get("provider_jobs_available", [])
            elif tab == "ongoing":
                jobs = DB.get("provider_jobs_ongoing", [])
            else:
                jobs = DB.get("provider_jobs_history", [])
            return self.reply_json({"count": len(jobs), "next": None, "previous": None, "results": jobs})

        # 15. Admin Analytics
        if path == "/api/admin/analytics/summary/":
            return self.reply_json(DB.get("admin_analytics_summary", {"total_orders": 1420, "revenue_bdt": 485000, "active_providers": 68}))
        if path == "/api/admin/analytics/heatmap/":
            return self.reply_json(DB.get("admin_analytics_heatmap", []))
        if path == "/api/admin/analytics/forecast/":
            return self.reply_json(DB.get("admin_analytics_forecast", {"trend": "upward", "predicted_growth": "18%"}))
        if path == "/api/admin/analytics/churn/":
            return self.reply_json(DB.get("admin_analytics_churn", []))
        if path == "/api/admin/analytics/fraud/":
            return self.reply_json(DB.get("admin_analytics_fraud", []))
        if path == "/api/admin/analytics/revenue/":
            return self.reply_json(DB.get("admin_analytics_revenue", {}))

        # Admin lists
        if path.startswith("/api/admin/providers/"):
            provs = DB.get("admin_providers", [])
            return self.reply_json({"count": len(provs), "results": provs})
        if path.startswith("/api/admin/orders/"):
            ords = DB.get("admin_orders", [])
            return self.reply_json({"count": len(ords), "results": ords})
        if path == "/api/admin/training-modules/":
            return self.reply_json(DB.get("admin_training", []))
        if path == "/api/admin/insurance-plans/":
            return self.reply_json(DB.get("admin_insurance", []))
        if path == "/api/admin/safety/":
            return self.reply_json(DB.get("admin_safety", []))

        # Fallback
        self.reply_json({"detail": "Not found"}, 404)

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        body = self.read_body()

        # 1. Auth (Login & Register)
        if path == "/api/auth/login/":
            phone = body.get("phone", "01711000001")
            user = DEMO_USERS.get(phone)
            if not user:
                role = "admin" if phone == "01700000000" else ("provider" if phone.startswith("018") else "customer")
                user = {"id": int(phone[-4:]) if phone[-4:].isdigit() else 101, "phone": phone, "full_name": "ব্যবহারকারী", "role": role, "is_verified": True}
            tok = make_jwt({"user_id": user["id"], "phone": user["phone"], "role": user["role"], "full_name": user["full_name"]})
            return self.reply_json({"access": tok, "refresh": tok, "user": user})

        if path == "/api/auth/register/":
            phone = body.get("phone", "01711000001")
            name = body.get("full_name", "ব্যবহারকারী")
            user = {"id": 999, "phone": phone, "full_name": name, "role": "customer", "is_verified": True}
            tok = make_jwt({"user_id": user["id"], "phone": user["phone"], "role": "customer", "full_name": name})
            return self.reply_json({"access": tok, "refresh": tok, "user": user}, 201)

        if path == "/api/auth/token/refresh/":
            tok = body.get("refresh", "")
            return self.reply_json({"access": tok})

        # 2. AI Photo Quote
        if path == "/api/custom-requests/ai-quote/":
            desc = body.get("description", "").lower()
            photo = body.get("photo_url", "")
            issue = "এয়ার কন্ডিশনার লিকেজ ও গ্যাস প্রেসার সমস্যা"
            cost_min, cost_max = 800, 1500
            slug = "ac-cleaning"
            severity = "medium"

            if "পাইপ" in desc or "লিক" in desc or "পানি" in desc or "pipe" in photo:
                issue = "সিঙ্কের নিচের ড্রেন পাইপ আলগা ও জোড়া লিকেজ"
                cost_min, cost_max = 350, 750
                slug = "plumber-visit"
                severity = "high"
            elif "শর্ট" in desc or "সকেট" in desc or "আগুন" in desc or "কারেন্ট" in desc or "burnt" in photo:
                issue = "সকেট ওভারহিটিং ও শর্ট সার্কিট ঝুঁকি"
                cost_min, cost_max = 500, 1200
                slug = "electrician-visit"
                severity = "critical"

            return self.reply_json({
                "id": int(time.time()),
                "photo_url": photo,
                "description": body.get("description", ""),
                "detected_issue": issue,
                "severity": severity,
                "estimated_cost_min": str(cost_min),
                "estimated_cost_max": str(cost_max),
                "recommended_service_slug": slug,
                "safety_advice_bn": "মেরামতের পূর্বে পাওয়ার মেইন সুইচ অথবা পানির মেইন ভালভ বন্ধ রাখুন।",
                "estimated_time_minutes": 45,
                "created_at": datetime.now().isoformat(),
            }, 201)

        # 3. Cart
        if path == "/api/cart/items/":
            user = self.get_user()
            uid = user["id"] if user else 101
            slug = body.get("slug", "")
            qty = body.get("quantity", 1)
            srvs = DB.get("services", [])
            prods = DB.get("products", [])
            item = next((s for s in srvs if s.get("slug") == slug), None) or next((p for p in prods if p.get("slug") == slug), None) or {"name_bn": slug, "base_price": 500}
            price = item.get("base_price", item.get("price", 500))
            cart_item = {
                "id": int(time.time()),
                "slug": slug,
                "name": item.get("name_bn", slug),
                "item_type": body.get("item_type", "service"),
                "quantity": qty,
                "unit_price": str(price),
                "total_price": str(float(price) * qty),
            }
            CARTS.setdefault(uid, []).append(cart_item)
            return self.reply_json(cart_item, 201)

        # 4. Orders
        if path == "/api/orders/":
            user = self.get_user()
            uid = user["id"] if user else 101
            order_id = int(time.time() % 100000)
            landlord_phone = body.get("landlord_phone", "")
            new_order = {
                "id": order_id,
                "status": "confirmed",
                "total_amount": "800.00",
                "contact_name": body.get("contact_name", "রহিম উদ্দিন"),
                "contact_phone": body.get("contact_phone", "01711000001"),
                "address_line": body.get("address_line", "ধানমন্ডি, ঢাকা"),
                "payment_method": body.get("payment_method", "cod"),
                "landlord_phone": landlord_phone,
                "landlord_approval_status": "pending" if landlord_phone else "none",
                "created_at": datetime.now().isoformat(),
                "bookings": [{
                    "id": order_id * 10,
                    "service_name_bn": "এসি সার্ভিসিং",
                    "status": "confirmed",
                    "scheduled_date": (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d"),
                    "slot": "09-11",
                    "provider_name": "করিম মিয়া",
                    "provider_phone": "01811000001",
                    "arrival_code": "4829",
                }]
            }
            DB.setdefault("customer_orders", []).insert(0, new_order)
            CARTS[uid] = []
            return self.reply_json(new_order, 201)

        if path.startswith("/api/orders/") and path.endswith("/landlord-approve/"):
            oid = path.strip("/").split("/")[2]
            receipt_no = f"RDR-2026-{oid}"
            for o in DB.get("customer_orders", []):
                if str(o.get("id")) == str(oid):
                    o["landlord_approval_status"] = "approved"
                    o["rent_deduction_receipt_number"] = receipt_no
            return self.reply_json({"id": int(oid) if oid.isdigit() else 1, "landlord_approval_status": "approved", "rent_deduction_receipt_number": receipt_no})

        # 5. Join Group Deal
        if path.startswith("/api/group-deals/") and path.endswith("/join/"):
            did = path.strip("/").split("/")[2]
            for d in DB.get("group_deals", []):
                if str(d.get("id")) == str(did):
                    d["current_participants"] = d.get("current_participants", 1) + 1
                    if d["current_participants"] >= d.get("target_participants", 4):
                        d["is_locked_in"] = True
                    return self.reply_json({"joined": True, "current_participants": d["current_participants"], "is_locked_in": d.get("is_locked_in", False)})
            return self.reply_json({"joined": True, "current_participants": 3, "is_locked_in": False})

        # 6. Home Profile
        if path == "/api/home-profiles/":
            new_home = {
                "id": int(time.time()),
                "name": body.get("name", "বাসা"),
                "address": body.get("address", "ধানমন্ডি"),
                "health_score": 88,
                "occupancy_mode": body.get("occupancy_mode", "tenant"),
                "landlord_name": body.get("landlord_name", "বাড়িওয়ালা"),
                "landlord_phone": body.get("landlord_phone", "01811000000"),
                "reminders": [
                    {"id": 1, "title_bn": "এসি ফিল্টার পরিষ্কার করুন", "due_date": (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d"), "is_completed": False},
                    {"id": 2, "title_bn": "ওয়াটার পিউরিফায়ার কার্ট্রিজ পরিবর্তন", "due_date": (datetime.now() + timedelta(days=14)).strftime("%Y-%m-%d"), "is_completed": False},
                ]
            }
            DB.setdefault("home_profiles", []).insert(0, new_home)
            return self.reply_json(new_home, 201)

        if "/complete-reminder/" in path:
            return self.reply_json({"is_completed": True})

        # 7. Provider Actions
        if path.startswith("/api/providers/jobs/") and path.endswith("/accept/"):
            return self.reply_json({"accepted": True, "status": "on_the_way"})

        if path == "/api/providers/earnings/instant-payout/":
            return self.reply_json({"success": True, "amount_pushed": "8450.00", "bkash_trx_id": "TRX98273645"})

        if "/training/" in path and path.endswith("/submit/"):
            return self.reply_json({"passed": True, "score": 100, "certificate_url": "/media/public/demo/cert.pdf"})

        # Fallback 200 for other POST actions
        self.reply_json({"status": "success", **body}, 200)

    def do_PATCH(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        body = self.read_body()
        if "/cart/items/" in path:
            return self.reply_json({"quantity": body.get("quantity", 1)})
        if path == "/api/providers/me/":
            return self.reply_json({"is_online": body.get("is_online", True)})
        self.reply_json({"status": "updated", **body}, 200)

    def do_DELETE(self):
        self.reply_json({"status": "deleted"}, 200)

    def log_message(self, format, *args):
        # Keep console output tidy
        print(f"[{datetime.now().strftime('%H:%M:%S')}] {args[0]} -> {args[1]}")


def run():
    server = http.server.ThreadingHTTPServer(("0.0.0.0", PORT), StandaloneHandler)
    print("=" * 65)
    print("  🚀 ShohorSathi Standalone Zero-Docker Backend Server")
    print(f"  ✓ Running on: http://localhost:{PORT}")
    print(f"  ✓ Database: Loaded {len(DB)} collections from {DB_FILE.name}")
    print("  ✓ Ready for Customer, Provider & Admin web apps!")
    print("=" * 65)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping standalone server.")
        server.server_close()


if __name__ == "__main__":
    run()
