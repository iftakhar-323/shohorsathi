import { expect, test, type Page } from "@playwright/test";

// Visits every page of the three apps on the demo data (scripts/seed_demo.py) and fails on JavaScript errors,
// failed API calls or an empty page. Full-page screenshots go to test-results/tour/ for a visual check.
const GATEWAY = process.env.GATEWAY_URL ?? "http://localhost:8088";
const APPS = { customer: "http://localhost:5173", provider: "http://localhost:5174", admin: "http://localhost:5175" };
const DEMO = { admin: "01700000000", customer: "01711000001", provider: "01811000001", password: "demo1234" };

type Tokens = { access: string; refresh: string };

async function tokens(phone: string, page: Page): Promise<Tokens> {
  const res = await page.request.post(`${GATEWAY}/api/auth/login/`, { data: { phone, password: DEMO.password } });
  expect(res.ok(), `login ${phone}`).toBeTruthy();
  return res.json();
}

async function api<T>(page: Page, t: Tokens, path: string): Promise<T> {
  const res = await page.request.get(`${GATEWAY}${path}`, { headers: { Authorization: `Bearer ${t.access}` } });
  expect(res.ok(), path).toBeTruthy();
  return res.json();
}

/** Open a page, wait for its data, and check it rendered without errors. */
async function visit(page: Page, url: string, shot: string, expectText?: string | RegExp) {
  const problems: string[] = [];
  page.removeAllListeners("pageerror");
  page.removeAllListeners("response");
  page.on("pageerror", (e) => problems.push(`JS error: ${e.message}`));
  page.on("response", (r) => {
    const u = r.url();
    if (u.includes("/api/") && r.status() >= 400 && !u.includes("/token/refresh/")) problems.push(`${r.status()} ${r.request().method()} ${u}`);
  });
  await page.goto(url);
  await page.waitForLoadState("networkidle");
  await page.waitForTimeout(400);
  const body = (await page.locator("main, body").first().innerText()).trim();
  expect(body.length, `${url} rendered nothing`).toBeGreaterThan(40);
  if (expectText) await expect(page.locator("body")).toContainText(expectText);
  await page.screenshot({ path: `test-results/tour/${shot}.png`, fullPage: true });
  expect(problems, `${url}\n${problems.join("\n")}`).toEqual([]);
}

test.describe.configure({ mode: "serial" });

test("customer app: every page", async ({ page }) => {
  test.setTimeout(240_000);
  const t = await tokens(DEMO.customer, page);
  const orders = await api<{ results: { id: number }[] }>(page, t, "/api/orders/");
  const requests = await api<{ results: { id: number }[] }>(page, t, "/api/custom-requests/");
  const issues = await api<{ results: { id: number }[] }>(page, t, "/api/issues/");
  const services = await api<{ results: { slug: string }[] }>(page, t, "/api/services/");
  const subs = await api<{ results: { id: number }[] }>(page, t, "/api/subscriptions/plans/").catch(() => ({ results: [] }));
  const C = APPS.customer;

  // public pages first, signed out
  for (const [path, name, text] of [
    ["/", "home", "ভরসাযোগ্য সমাধান"], ["/services", "services", "এসি ক্লিনিং"], [`/services/${services.results[0].slug}`, "service-detail", undefined],
    ["/shop", "shop", "এলইডি"], ["/subscriptions", "subscriptions", undefined], ["/issues", "issues", "ময়লার"], [`/issues/${issues.results[0].id}`, "issue-detail", undefined],
    ["/community", "community", undefined], ["/transparency", "transparency", "ওয়ার্ড ৭"], ["/privacy", "privacy", undefined], ["/terms", "terms", undefined],
    ["/business", "business", undefined], ["/login", "login", undefined], ["/register", "register", undefined],
  ] as [string, string, string | undefined][]) {
    await visit(page, C + path, `customer-${name}`, text);
  }

  await page.addInitScript((tk) => localStorage.setItem("shohor.tokens", JSON.stringify(tk)), t);
  for (const [path, name, text] of [
    ["/", "home-signed-in", "মৌসুমি প্যাকেজ"], ["/orders", "orders", undefined], [`/orders/${orders.results.at(-1)!.id}`, "order-detail", "সম্পন্ন"],
    [`/orders/${orders.results[0].id}`, "order-detail-upcoming", undefined], ["/cart", "cart", undefined], ["/custom-requests", "custom-requests", undefined],
    [`/custom-requests/${requests.results[0].id}`, "custom-request-detail", undefined], ["/custom-requests/new", "custom-request-new", undefined],
    ["/subscriptions/mine", "subscriptions-mine", undefined], ["/issues/mine", "issues-mine", undefined], ["/issues/new", "issue-new", undefined],
    ["/ai-quote", "ai-quote", undefined], ["/home-profile", "home-profile", "ধানমন্ডির বাসা"], ["/wallet", "wallet", undefined], ["/profile", "profile", undefined],
    ["/chat", "chat", undefined], ["/notifications", "notifications", undefined],
  ] as [string, string, string | undefined][]) {
    await visit(page, C + path, `customer-${name}`, text);
  }
  if (subs.results.length) await visit(page, `${C}/subscriptions`, "customer-subscriptions-signed-in");
});

test("customer app: main flows work by clicking", async ({ page }) => {
  test.setTimeout(120_000);
  const t = await tokens("01711000003", page);
  await page.addInitScript((tk) => localStorage.setItem("shohor.tokens", JSON.stringify(tk)), t);
  const C = APPS.customer;

  // book a service from its page to checkout
  await page.goto(`${C}/services/plumber-visit`);
  await page.getByRole("button", { name: "কার্টে যোগ করুন" }).click();
  await page.goto(`${C}/cart`);
  await expect(page.getByText("প্লাম্বার ভিজিট").first()).toBeVisible();
  await page.screenshot({ path: "test-results/tour/flow-cart.png", fullPage: true });

  // AI quote with a typed description
  await page.goto(`${C}/ai-quote`);
  await page.getByRole("textbox").last().fill("বাথরুমের পাইপ থেকে পানি পড়ছে");
  await page.getByRole("button", { name: /বিশ্লেষণ/ }).click();
  await expect(page.getByText("প্রস্তাবিত সার্ভিস")).toBeVisible();
  await page.screenshot({ path: "test-results/tour/flow-ai-quote.png", fullPage: true });

  // English switch keeps working on a data page
  await page.goto(`${C}/services`);
  await page.getByRole("button", { name: "Switch to English" }).click();
  await expect(page.getByText("AC cleaning").first()).toBeVisible();
  await page.screenshot({ path: "test-results/tour/flow-services-english.png", fullPage: true });
  await page.getByRole("button", { name: "বাংলায় দেখুন" }).click();
});

test("provider app: every page", async ({ page }) => {
  test.setTimeout(120_000);
  const t = await tokens(DEMO.provider, page);
  const jobs = await api<{ results: { id: number }[] }>(page, t, "/api/providers/jobs/?tab=history");
  await page.addInitScript((tk) => localStorage.setItem("shohor.tokens", JSON.stringify(tk)), t);
  const P = APPS.provider;
  for (const [path, name] of [["/", "inbox"], ["/schedule", "schedule"], ["/earnings", "earnings"], ["/training", "training"],
    ["/insurance", "insurance"], ["/profile", "profile"], ["/chat", "chat"], ["/notifications", "notifications"]]) {
    await visit(page, P + path, `provider-${name}`);
  }
  expect(jobs.results.length, "the demo electrician has a finished job").toBeGreaterThan(0);
  await visit(page, `${P}/jobs/${jobs.results[0].id}`, "provider-job-detail", "গ্রাহককে রেটিং দিন");
});

test("admin app: every page", async ({ page }) => {
  test.setTimeout(240_000);
  const t = await tokens(DEMO.admin, page);
  await page.addInitScript((tk) => localStorage.setItem("shohor.tokens", JSON.stringify(tk)), t);
  const A = APPS.admin;
  for (const path of ["/", "/orders", "/jobs", "/custom-requests", "/providers", "/catalog", "/promotions", "/subscriptions", "/payments",
    "/safety", "/insurance", "/training", "/support", "/issues", "/analytics", "/business", "/loyalty", "/broadcast", "/payouts", "/warranty",
    "/areas", "/users"]) {
    await visit(page, A + path, `admin${path === "/" ? "-dashboard" : path.replaceAll("/", "-")}`);
  }
  // analytics tabs
  await page.goto(`${A}/analytics`);
  for (const tab of ["চাহিদার পূর্বাভাস", "হারানোর ঝুঁকিতে গ্রাহক", "জালিয়াতির সংকেত"]) {
    await page.getByRole("tab", { name: tab }).or(page.getByRole("button", { name: tab })).first().click();
    await page.waitForLoadState("networkidle");
    await page.waitForTimeout(800);
    await page.screenshot({ path: `test-results/tour/admin-analytics-${tab.split(" ")[0]}.png`, fullPage: true });
  }
});

test("mobile: key customer pages fit the screen @mobile", async ({ page }) => {
  const C = APPS.customer;
  for (const [path, name] of [["/", "home"], ["/services", "services"], ["/transparency", "transparency"]]) {
    await page.goto(C + path);
    await page.waitForLoadState("networkidle");
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
    expect(overflow, `${path} scrolls sideways`).toBeLessThanOrEqual(1);
    await page.screenshot({ path: `test-results/tour/mobile-${name}.png`, fullPage: true });
  }
});
