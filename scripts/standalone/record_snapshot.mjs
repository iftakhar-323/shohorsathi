// Records what the three apps receive from the real backend, for the no-Docker server (scripts/standalone_server.py).
// Run with the Docker stack on fresh demo data (scripts/up.sh --demo) and the apps running (pnpm dev):
//   node scripts/standalone/record_snapshot.mjs      → demo/data/standalone_snapshot.json
// Every GET /api/... response the apps get while visiting every page as every demo user (and as a visitor) is stored,
// keyed by user and by path + sorted query string.
import { createHash } from "node:crypto";
import { createRequire } from "node:module";
import fs from "node:fs";
import path from "node:path";

const ROOT = path.resolve(path.dirname(new URL(import.meta.url).pathname), "../..");
const require = createRequire(path.join(ROOT, "apps/e2e/package.json"));
const { chromium } = require("@playwright/test");

const GW = "http://localhost:8088";
const APP = { customer: "http://localhost:5173", provider: "http://localhost:5174", admin: "http://localhost:5175" };
const OUT = path.join(ROOT, "demo/data/standalone_snapshot.json");
const CUSTOMERS = ["01711000001", "01711000002", "01711000003", "01711000004", "01711000005", "01711000006", "01711000007", "01711000008"];
const PROVIDERS = ["01811000001", "01811000002", "01811000003", "01811000004", "01811000005", "01811000006", "01811000007"];
const ADMIN = "01700000000";

const bodies = {};   // sha1 -> JSON body
const routes = {};   // user -> { "path?query": sha1 }
const users = {};    // phone -> { me, claims }

export function routeKey(url) {
  const u = new URL(url);
  const q = [...u.searchParams.entries()].sort(([a], [b]) => a.localeCompare(b));
  return u.pathname + (q.length ? "?" + new URLSearchParams(q).toString() : "");
}

function store(user, key, body) {
  const json = JSON.stringify(body);
  const h = createHash("sha1").update(json).digest("hex").slice(0, 16);
  bodies[h] = body;
  (routes[user] ??= {})[key] = h;
}

async function login(phone) {
  const r = await fetch(`${GW}/api/auth/login/`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ phone, password: "demo1234" }) });
  if (!r.ok) throw new Error(`login ${phone}: ${r.status}`);
  return r.json();
}

async function get(p, tk) {
  const r = await fetch(GW + p, { headers: tk ? { Authorization: `Bearer ${tk.access}` } : {} });
  return r.ok ? r.json() : null;
}

/** Also store an API response fetched directly (for endpoints a page calls only after a click). */
async function direct(user, tk, p) {
  const body = await get(p, tk);
  if (body !== null) store(user, routeKey(GW + p), body);
  return body;
}

const browser = await chromium.launch();
let pages = 0;

async function visit(user, tk, base, paths, cities = [""]) {
  for (const city of cities) {
    const ctx = await browser.newContext();
    await ctx.addInitScript(([t, c]) => {
      if (t) localStorage.setItem("shohor.tokens", JSON.stringify(t));
      if (c) localStorage.setItem("shohor.city", c); else localStorage.removeItem("shohor.city");
    }, [tk, city]);
    const page = await ctx.newPage();
    page.on("response", async (r) => {
      const u = new URL(r.url());
      if (r.request().method() !== "GET" || !u.pathname.startsWith("/api/") || r.status() !== 200) return;
      try { store(user, routeKey(r.url()), await r.json()); } catch { /* not JSON */ }
    });
    for (const p of paths) {
      try {
        await page.goto(base + p, { timeout: 20000 });
        await page.waitForLoadState("networkidle", { timeout: 15000 });
        await page.waitForTimeout(300);
        pages++;
      } catch (e) { console.log(`  ! ${user} ${p}: ${e.message.slice(0, 80)}`); }
    }
    await ctx.close();
  }
}

const ids = (list) => (list?.results ?? list ?? []).map((x) => x.id);

// ---------- visitor ----------
const services = await get("/api/services/");
const plans = await get("/api/subscription-plans/");
const allIssues = await get("/api/issues/?status=");
const guestPages = ["/", "/services", "/shop", "/subscriptions", "/issues", "/transparency", "/community", "/login", "/register", "/privacy", "/terms",
  ...services.results.map((s) => `/services/${s.slug}`), ...plans.map((p) => `/subscriptions/new/${p.slug}`), ...ids(allIssues).map((i) => `/issues/${i}`)];
await visit("guest", null, APP.customer, guestPages, ["", "Dhaka", "Khulna", "Chattogram"]);
for (const s of services.results) await direct("guest", null, `/api/services/${s.slug}/`);
for (const p of (await get("/api/products/")).results) await direct("guest", null, `/api/products/${p.slug}/`);
await direct("guest", null, "/api/products/");
for (const pl of plans) await direct("guest", null, `/api/subscription-plans/${pl.slug}/`);
console.log("visitor done");

// ---------- customers ----------
for (const phone of CUSTOMERS) {
  const tk = await login(phone);
  users[phone] = { tokens_claims: JSON.parse(Buffer.from(tk.access.split(".")[1], "base64url").toString()), me: await get("/api/me/", tk) };
  const orders = await get("/api/orders/", tk);
  const reqs = await get("/api/custom-requests/", tk);
  const subs = await get("/api/subscriptions/", tk);
  const paths = ["/", "/services", "/shop", "/subscriptions", "/issues", "/issues/mine", "/issues/new", "/community", "/transparency", "/cart", "/orders",
    "/custom-requests", "/custom-requests/new", "/subscriptions/mine", "/ai-quote", "/home-profile", "/wallet", "/profile", "/chat", "/notifications",
    "/business", ...ids(orders).map((i) => `/orders/${i}`), ...ids(reqs).map((i) => `/custom-requests/${i}`), ...ids(subs).map((i) => `/subscriptions/${i}`),
    ...plans.map((p) => `/subscriptions/new/${p.slug}`), ...ids(allIssues).map((i) => `/issues/${i}`), ...services.results.map((s) => `/services/${s.slug}`)];
  const city = ["01711000004", "01711000005", "01711000006", "01711000007", "01711000008"].includes(phone) ? "Khulna" : "Dhaka";
  await visit(phone, tk, APP.customer, paths, ["", city]);
  for (const o of orders.results) await direct(phone, tk, `/api/orders/${o.id}/tracking/`);
  await direct(phone, tk, "/api/me/addresses/");
  await direct(phone, tk, "/api/loyalty/me/");
  console.log(`customer ${phone} done`);
}

// ---------- providers ----------
for (const phone of PROVIDERS) {
  const tk = await login(phone);
  users[phone] = { tokens_claims: JSON.parse(Buffer.from(tk.access.split(".")[1], "base64url").toString()), me: await get("/api/me/", tk) };
  const jobs = [];
  for (const tab of ["active", "available", "history"]) jobs.push(...ids(await direct(phone, tk, `/api/providers/jobs/?tab=${tab}`)));
  await visit(phone, tk, APP.provider, ["/", "/schedule", "/earnings", "/training", "/insurance", "/profile", "/chat", "/notifications",
    ...jobs.map((j) => `/jobs/${j}`)], ["", phone >= "01811000004" ? "Khulna" : "Dhaka"]);
  console.log(`provider ${phone} done`);
}

// ---------- admin ----------
{
  const tk = await login(ADMIN);
  users[ADMIN] = { tokens_claims: JSON.parse(Buffer.from(tk.access.split(".")[1], "base64url").toString()), me: await get("/api/me/", tk) };
  await visit(ADMIN, tk, APP.admin, ["/", "/orders", "/jobs", "/custom-requests", "/providers", "/catalog", "/promotions", "/subscriptions", "/payments",
    "/safety", "/insurance", "/training", "/support", "/issues", "/analytics", "/business", "/loyalty", "/broadcast", "/payouts", "/warranty", "/areas", "/users"]);
  for (const st of ["pending", "approved", "rejected", "suspended", ""]) await direct(ADMIN, tk, `/api/admin/providers/?status=${st}`);
  for (const city of ["Dhaka", "Khulna", "Chattogram"]) {
    for (const p of ["summary", "heatmap", "forecast", "churn", "revenue"]) await direct(ADMIN, tk, `/api/admin/analytics/${p}/?city=${city}&days=30`);
  }
  for (const p of ["forecast", "churn", "fraud", "revenue"]) await direct(ADMIN, tk, `/api/admin/analytics/${p}/?days=30`);
  await direct(ADMIN, tk, "/api/admin/analytics/forecast/");
  await direct(ADMIN, tk, "/api/admin/analytics/churn/");
  await direct(ADMIN, tk, "/api/catalog/sponsored/");
  await direct(ADMIN, tk, "/api/seasonal-packages/");
  await direct(ADMIN, tk, "/api/admin/authorities/");
  console.log("admin done");
}

await browser.close();
fs.mkdirSync(path.dirname(OUT), { recursive: true });
fs.writeFileSync(OUT, JSON.stringify({ recorded_at: new Date().toISOString(), users, routes, bodies }));
const n = Object.values(routes).reduce((a, r) => a + Object.keys(r).length, 0);
console.log(`\n${pages} pages visited; ${n} routes, ${Object.keys(bodies).length} distinct bodies → ${OUT} (${(fs.statSync(OUT).size / 1e6).toFixed(1)} MB)`);
