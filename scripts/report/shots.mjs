// Screenshots of the whole ShohorSathi website with Khulna selected, signed in as each kind of user.
// Needs the stack with demo data (scripts/up.sh --demo) and the three apps (pnpm dev).
// Run from the repo root: node scripts/report/shots.mjs   → report-out/shots/*.png
import { createRequire } from "node:module";
import fs from "node:fs";
import path from "node:path";

const ROOT = path.resolve(path.dirname(new URL(import.meta.url).pathname), "../..");
const require = createRequire(path.join(ROOT, "apps/e2e/package.json"));
const { chromium } = require("@playwright/test");

const OUT = path.join(ROOT, "report-out/shots/");
fs.mkdirSync(OUT, { recursive: true });
const GW = "http://localhost:8088";
const C = "http://localhost:5173", P = "http://localhost:5174", A = "http://localhost:5175";
const PASSWORD = "demo1234";
const problems = [];
let count = 0;

const browser = await chromium.launch();

async function login(phone) {
  const r = await fetch(`${GW}/api/auth/login/`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ phone, password: PASSWORD }) });
  if (!r.ok) throw new Error(`login ${phone}: ${r.status}`);
  return r.json();
}
async function get(p, tk) {
  const r = await fetch(GW + p, { headers: tk ? { Authorization: `Bearer ${tk.access}` } : {} });
  return r.json();
}

async function context({ tokens, mobile = false } = {}) {
  const ctx = await browser.newContext(mobile
    ? { viewport: { width: 390, height: 844 }, deviceScaleFactor: 2, isMobile: true, hasTouch: true }
    : { viewport: { width: 1440, height: 900 }, deviceScaleFactor: 1.5 });
  await ctx.addInitScript((tk) => {
    localStorage.setItem("shohor.city", "Khulna");
    if (tk) localStorage.setItem("shohor.tokens", JSON.stringify(tk));
  }, tokens ?? null);
  const page = await ctx.newPage();
  page.on("pageerror", (e) => problems.push(`${page.url()} JS error: ${e.message}`));
  page.on("response", (r) => {
    if (r.url().includes("/api/") && r.status() >= 400 && !r.url().includes("/token/refresh/")) problems.push(`${page.url()} → ${r.status()} ${r.url()}`);
  });
  return { ctx, page };
}

const tab = (label) => (p) => p.getByRole("tab", { name: label }).or(p.getByRole("button", { name: label })).first().click();

async function shot(page, name, url, { act, full = true } = {}) {
  if (url) await page.goto(url);
  await page.waitForLoadState("networkidle");
  if (act) { await act(page); await page.waitForLoadState("networkidle"); }
  await page.waitForTimeout(900);
  await page.screenshot({ path: `${OUT}${name}.png`, fullPage: full });
  count++;
  console.log("✓", name);
}

// ---------- customer site, Khulna selected, signed out ----------
{
  const { ctx, page } = await context();
  const issues = (await get("/api/issues/?city=Khulna&status=")).results;
  const byTitle = (t) => issues.find((i) => i.title.startsWith(t)).id;
  await shot(page, "c01-home", C + "/");
  await shot(page, "c02-services", C + "/services");
  await shot(page, "c03-service-detail", C + "/services/ac-cleaning");
  await shot(page, "c04-shop", C + "/shop");
  await shot(page, "c05-subscription-plans", C + "/subscriptions");
  await shot(page, "c06-issues-khulna", C + "/issues");
  await shot(page, "c07-issue-mosquito", `${C}/issues/${byTitle("নিরালায় মশার")}`);
  await shot(page, "c08-issue-resolved", `${C}/issues/${byTitle("ময়লাপোতা মোড়ে")}`);
  await shot(page, "c09-issue-rejected", `${C}/issues/${byTitle("লবণচরায় ফুটপাত")}`);
  await shot(page, "c10-transparency", C + "/transparency");
  await shot(page, "c11-community-khulna", C + "/community");
  await shot(page, "c12-login", C + "/login", { full: false });
  await shot(page, "c14-home-english", C + "/services", { act: (p) => p.getByRole("button", { name: "Switch to English" }).click() });
  await ctx.close();
}

// ---------- customer: আরিফ (Khalishpur) ----------
{
  const tk = await login("01711000005");
  const { ctx, page } = await context({ tokens: tk });
  const orders = (await get("/api/orders/", tk)).results;
  const ac = orders.find((o) => o.bookings[0]?.service_name?.includes("এসি"));
  const plumber = orders.find((o) => o.bookings[0]?.service_name?.includes("প্লাম্বার"));
  const reqs = (await get("/api/custom-requests/", tk)).results;
  await shot(page, "a01-home-signed-in", C + "/");
  await shot(page, "a02-orders", C + "/orders");
  await shot(page, "a03-order-done-reviewed", `${C}/orders/${ac.id}`);
  await shot(page, "a04-order-waiting", `${C}/orders/${plumber.id}`);
  await shot(page, "a05-custom-requests", C + "/custom-requests");
  await shot(page, "a06-custom-request-quote", `${C}/custom-requests/${reqs.find((r) => r.service_type.includes("আইপিএস")).id}`);
  await shot(page, "a07-notifications", C + "/notifications");
  await shot(page, "a08-wallet-points", C + "/wallet");
  await shot(page, "a10-my-issues", C + "/issues/mine");
  await shot(page, "a11-ai-quote", C + "/ai-quote", {
    act: async (p) => {
      await p.getByRole("textbox").last().fill("রান্নাঘরের সিংকের নিচে পাইপ থেকে পানি পড়ছে");
      await p.getByRole("button", { name: /বিশ্লেষণ/ }).click();
      await p.getByText("প্রস্তাবিত সার্ভিস").waitFor();
    },
  });
  await shot(page, "a12-cart", C + "/services/kitchen-deep-clean", {
    act: async (p) => { await p.getByRole("button", { name: "কার্টে যোগ করুন" }).click(); await p.goto(C + "/cart"); },
  });
  await shot(page, "a13-checkout", C + "/checkout");
  await shot(page, "a14-new-issue-form", C + "/issues/new");
  // leave the cart empty again
  for (const it of (await get("/api/cart/", tk)).items) await fetch(`${GW}/api/cart/items/${it.id}/`, { method: "DELETE", headers: { Authorization: `Bearer ${tk.access}` } });
  await ctx.close();
}

// ---------- customer: সুমাইয়া (Boyra) and তাসলিমা (Dakbangla) ----------
{
  const tk = await login("01711000006");
  const { ctx, page } = await context({ tokens: tk });
  const subs = (await get("/api/subscriptions/", tk)).results;
  await shot(page, "s01-subscriptions-mine", C + "/subscriptions/mine");
  if (subs[0]) await shot(page, "s02-subscription-detail", `${C}/subscriptions/${subs[0].id}`);
  await shot(page, "s03-home-profile", C + "/home-profile");
  const orders = (await get("/api/orders/", tk)).results;
  await shot(page, "s04-order-confirmed-female-cleaner", `${C}/orders/${orders.find((o) => o.bookings[0]?.service_name?.includes("ডিপ")).id}`);
  await ctx.close();
}
{
  const tk = await login("01711000008");
  const { ctx, page } = await context({ tokens: tk });
  const orders = (await get("/api/orders/", tk)).results;
  await shot(page, "t02-order-painting", `${C}/orders/${orders.find((o) => o.bookings[0]?.service_name?.includes("রং")).id}`);
  await shot(page, "t03-home-profile-tenant", C + "/home-profile");
  await ctx.close();
}

// ---------- provider: সাইফুল (AC & plumbing) and রেহানা (cleaner) ----------
{
  const tk = await login("01811000006");
  const { ctx, page } = await context({ tokens: tk });
  const done = (await get("/api/providers/jobs/?tab=history", tk)).results;
  await shot(page, "p01-inbox", P + "/");
  await shot(page, "p02-new-jobs", P + "/", { act: tab("নতুন কাজ") });
  await shot(page, "p03-history", P + "/", { act: tab("ইতিহাস") });
  await shot(page, "p04-job-done", `${P}/jobs/${done[0].id}`);
  await shot(page, "p05-earnings", P + "/earnings");
  await shot(page, "p07-training", P + "/training");
  await shot(page, "p08-insurance", P + "/insurance");
  await shot(page, "p09-profile", P + "/profile");
  await ctx.close();
}
{
  const tk = await login("01811000005");
  const { ctx, page } = await context({ tokens: tk });
  const active = (await get("/api/providers/jobs/?tab=active", tk)).results;
  if (active[0]) await shot(page, "r02-job-accepted", `${P}/jobs/${active[0].id}`);
  await shot(page, "r03-training-certificate", P + "/training");
  await ctx.close();
}

// ---------- admin ----------
{
  const tk = await login("01700000000");
  const { ctx, page } = await context({ tokens: tk });
  await shot(page, "m01-dashboard", A + "/");
  await shot(page, "m02-orders", A + "/orders");
  await shot(page, "m03-jobs", A + "/jobs");
  await shot(page, "m04-custom-requests", A + "/custom-requests");
  await shot(page, "m05-providers", A + "/providers", { act: tab("অনুমোদিত") });
  await shot(page, "m06-issues", A + "/issues");
  await shot(page, "m07-authorities", A + "/issues", { act: tab("কর্তৃপক্ষ") });
  await shot(page, "m08-analytics-khulna", A + "/analytics", { act: (p) => p.locator("select").nth(1).selectOption("Khulna") });
  await shot(page, "m09-forecast-khulna", null, { act: tab("চাহিদার পূর্বাভাস") });
  await shot(page, "m10-churn", null, { act: tab("হারানোর ঝুঁকিতে গ্রাহক") });
  await shot(page, "m11-fraud", null, { act: tab("জালিয়াতির সংকেত") });
  await shot(page, "m12-group-deals", A + "/promotions");
  await shot(page, "m13-seasonal", A + "/promotions", { act: tab("মৌসুমি প্যাকেজ") });
  await shot(page, "m14-sponsored", A + "/promotions", { act: tab("স্পন্সরড লিস্টিং") });
  await shot(page, "m15-subscriptions", A + "/subscriptions");
  await shot(page, "m17-areas", A + "/areas");
  await shot(page, "m18-users", A + "/users");
  await shot(page, "m20-safety", A + "/safety");
  await shot(page, "m22-training", A + "/training");
  await shot(page, "m24-broadcast", A + "/broadcast");
  await ctx.close();
}

// ---------- phone ----------
{
  const tk = await login("01711000005");
  const { ctx, page } = await context({ tokens: tk, mobile: true });
  const orders = (await get("/api/orders/", tk)).results;
  await shot(page, "x01-mobile-home", C + "/");
  await shot(page, "x02-mobile-issues", C + "/issues");
  await shot(page, "x03-mobile-order", `${C}/orders/${orders.at(-1).id}`);
  await shot(page, "x04-mobile-transparency", C + "/transparency");
  await ctx.close();
}

await browser.close();
fs.writeFileSync(`${OUT}problems.json`, JSON.stringify(problems, null, 1));
console.log(`\n${count} screenshots; ${problems.length} problems`);
for (const p of problems) console.log("  !", p);
