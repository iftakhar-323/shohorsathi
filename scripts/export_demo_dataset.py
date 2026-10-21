"""Export all seeded data from running Docker stack into demo/standalone_db.json.
This enables running the entire ShohorSathi stack WITHOUT Docker on Windows/Mac/Linux.
"""
import json
import os
import urllib.request

BASE = "http://localhost:8088"

def get(path, token=None):
    req = urllib.request.Request(f"{BASE}{path}")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        print(f"Failed {path}: {e}")
        return None

def post(path, body):
    req = urllib.request.Request(
        f"{BASE}{path}",
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        print(f"Failed POST {path}: {e}")
        return None

def to_list_or_dict(data):
    if not data:
        return []
    if isinstance(data, dict):
        return data.get("results", data)
    return data

def main():
    db = {}
    print("Logging in demo accounts...")
    admin_tokens = post("/api/auth/login/", {"phone": "01700000000", "password": "demo1234"}) or {}
    admin_tok = admin_tokens.get("access")
    
    cust_tokens = post("/api/auth/login/", {"phone": "01711000001", "password": "demo1234"}) or {}
    cust_tok = cust_tokens.get("access")

    prov_tokens = post("/api/auth/login/", {"phone": "01811000001", "password": "demo1234"}) or {}
    prov_tok = prov_tokens.get("access")

    endpoints = [
        ("categories", "/api/categories/?page_size=100"),
        ("services", "/api/services/?page_size=100"),
        ("products", "/api/products/?page_size=100"),
        ("areas", "/api/areas/"),
        ("issues", "/api/issues/?page_size=100"),
        ("transparency", "/api/issues/transparency/"),
        ("group_deals", "/api/group-deals/"),
        ("seasonal_packages", "/api/seasonal-packages/"),
        ("subscription_plans", "/api/subscription-plans/"),
        ("community_posts", "/api/community/posts/?page_size=100"),
    ]

    for key, path in endpoints:
        print(f"Fetching {key} from {path}...")
        data = get(path)
        if data is not None:
            db[key] = to_list_or_dict(data)

    if admin_tok:
        print("Fetching admin data...")
        db["authorities"] = to_list_or_dict(get("/api/admin/authorities/", admin_tok))
        db["admin_providers"] = to_list_or_dict(get("/api/admin/providers/?page_size=100", admin_tok))
        db["admin_orders"] = to_list_or_dict(get("/api/admin/orders/?page_size=100", admin_tok))
        db["admin_training"] = to_list_or_dict(get("/api/admin/training-modules/", admin_tok))
        db["admin_insurance"] = to_list_or_dict(get("/api/admin/insurance-plans/", admin_tok))
        db["admin_safety"] = to_list_or_dict(get("/api/admin/safety/", admin_tok))
        db["admin_analytics_summary"] = get("/api/admin/analytics/summary/", admin_tok) or {}
        db["admin_analytics_heatmap"] = get("/api/admin/analytics/heatmap/", admin_tok) or []
        db["admin_analytics_forecast"] = get("/api/admin/analytics/forecast/", admin_tok) or {}
        db["admin_analytics_churn"] = get("/api/admin/analytics/churn/", admin_tok) or []
        db["admin_analytics_fraud"] = get("/api/admin/analytics/fraud/", admin_tok) or []
        db["admin_analytics_revenue"] = get("/api/admin/analytics/revenue/", admin_tok) or {}

    if cust_tok:
        print("Fetching customer orders and home profiles...")
        db["customer_orders"] = to_list_or_dict(get("/api/orders/?page_size=100", cust_tok))
        db["home_profiles"] = to_list_or_dict(get("/api/home-profiles/", cust_tok))

    if prov_tok:
        print("Fetching provider jobs and earnings...")
        db["provider_me"] = get("/api/providers/me/", prov_tok) or {}
        db["provider_earnings"] = get("/api/providers/earnings/", prov_tok) or {}
        db["provider_jobs_available"] = to_list_or_dict(get("/api/providers/jobs/?tab=available", prov_tok))
        db["provider_jobs_ongoing"] = to_list_or_dict(get("/api/providers/jobs/?tab=ongoing", prov_tok))
        db["provider_jobs_history"] = to_list_or_dict(get("/api/providers/jobs/?tab=history", prov_tok))

    os.makedirs("demo/data", exist_ok=True)
    out_file = "demo/data/standalone_db.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(db, f, ensure_ascii=False, indent=2)
    print(f"Exported {len(db)} collections to {out_file} ({os.path.getsize(out_file)} bytes)!")

if __name__ == "__main__":
    main()
