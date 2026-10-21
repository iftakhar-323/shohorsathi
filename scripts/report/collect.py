"""Fetch the Khulna demo records the report's tables are built from → report-out/data.json.
Run from the repo root with the stack and demo data up: python3 scripts/report/collect.py"""
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
import e2e_phase1 as e1  # noqa: E402

call = e1.call
OUT = pathlib.Path(__file__).resolve().parents[2] / "report-out"
OUT.mkdir(exist_ok=True)


def allpages(path, tk=None):
    out, n = [], 1
    while True:
        d = call("GET", path + ("&" if "?" in path else "?") + f"page={n}", tk)
        if isinstance(d, list):
            return d
        out += d.get("results", [])
        if not d.get("next"):
            return out
        n += 1


admin = call("POST", "/api/auth/login/", body={"phone": "01700000000", "password": "demo1234"}, expect=200)["access"]
areas = call("GET", "/api/areas/?city=Khulna")
ids = {a["id"] for a in areas}
data = {
    "areas": areas,
    "all_areas": call("GET", "/api/areas/"),
    "issues": [i for i in allpages("/api/admin/issues/", admin) if i["area_id"] in ids],
    "orders": [o for o in allpages("/api/admin/orders/", admin) if o["area_id"] in ids],
    "jobs": [j for j in allpages("/api/admin/jobs/", admin) if j.get("area_id") in ids],
    "providers": [p for p in allpages("/api/admin/providers/?status=approved", admin) if set(p["area_ids"]) & ids],
    "authorities": call("GET", "/api/admin/authorities/", admin),
    "posts": allpages("/api/community/posts/?city=Khulna"),
    "deals": allpages("/api/group-deals/"),
    "transparency": call("GET", "/api/issues/transparency/?days=90&city=Khulna"),
    "summary": call("GET", "/api/admin/analytics/summary/?days=30&city=Khulna", admin),
    "custom_requests": [c for c in allpages("/api/admin/custom-requests/?status=", admin) if c.get("area_id") in ids],
}
data["reviews"] = {p["id"]: call("GET", f"/api/providers/public/{p['id']}/reviews/").get("results", []) for p in data["providers"]}
(OUT / "data.json").write_text(json.dumps(data, ensure_ascii=False, indent=1))
print({k: len(v) for k, v in data.items() if isinstance(v, (list, dict))})
