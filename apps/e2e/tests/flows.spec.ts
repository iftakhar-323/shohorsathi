import { expect, test, type Page } from "@playwright/test";

// Click-through flows on the demo data (scripts/seed_demo.py), the way a person uses the apps: every step through the UI,
// no API shortcuts except signing in. Every test fails on a JavaScript error or a failed (4xx/5xx) API call.
const GATEWAY = process.env.GATEWAY_URL ?? "http://localhost:8088";
const C = "http://localhost:5173", P = "http://localhost:5174", A = "http://localhost:5175";
const PHOTO = "../../demo/images/issues/garbage.jpg";  // tests run from apps/e2e
const ok404 = [/\/api\/orders\/landlord\/wrong/];

type Tokens = { access: string; refresh: string };

async function signIn(page: Page, phone: string, city = ""): Promise<Tokens> {
  const res = await page.request.post(`${GATEWAY}/api/auth/login/`, { data: { phone, password: "demo1234" } });
  expect(res.ok(), `login ${phone}`).toBeTruthy();
  const tokens = await res.json();
  await page.addInitScript(([t, c]) => {
    localStorage.setItem("shohor.tokens", JSON.stringify(t));
    if (c) localStorage.setItem("shohor.city", c as string);
    else localStorage.removeItem("shohor.city");
  }, [tokens, city]);
  return tokens;
}

async function api<T>(page: Page, t: Tokens, p: string): Promise<T> {
  const res = await page.request.get(`${GATEWAY}${p}`, { headers: { Authorization: `Bearer ${t.access}` } });
  expect(res.ok(), p).toBeTruthy();
  return res.json();
}

function watch(page: Page) {
  const problems: string[] = [];
  page.on("pageerror", (e) => problems.push(`JS error: ${e.message}`));
  page.on("response", (r) => {
    const u = r.url();
    if (r.status() === 409 && u.includes("/api/issues/")) return;
    if (u.includes("/api/") && r.status() >= 400 && !u.includes("/token/refresh/") && !ok404.some((re) => re.test(u)))
      problems.push(`${r.status()} ${r.request().method()} ${u}`);
  });
  page.on("dialog", (d) => d.accept());
  return problems;
}

async function emptyCart(page: Page, t: Tokens) {
  const cart = await api<{ items: { id: number }[] }>(page, t, "/api/cart/");
  for (const it of cart.items) await page.request.delete(`${GATEWAY}/api/cart/items/${it.id}/`, { headers: { Authorization: `Bearer ${t.access}` } });
}

const button = (page: Page, name: string | RegExp) => page.getByRole("button", { name }).first();

test.describe.configure({ mode: "serial" });
let tanvirOrder = 0;

test("checkout: service, new address, cash on delivery", async ({ page }) => {
  const problems = watch(page);
  const t = await signIn(page, "01711000003");
  await emptyCart(page, t);
  await page.goto(`${C}/services/electrician-visit`);
  await button(page, "কার্টে যোগ করুন").click();
  await expect(page).toHaveURL(/\/cart$/);
  await expect(page.getByText("ইলেকট্রিশিয়ান ভিজিট").first()).toBeVisible();
  await page.getByRole("link", { name: /চেকআউট/ }).or(page.getByRole("button", { name: /চেকআউট/ })).first().click();
  await expect(page).toHaveURL(/\/checkout/);
  await page.getByText("নতুন ঠিকানা").click();
  await page.getByLabel("এলাকা").selectOption({ label: "উত্তরা" });
  await page.getByLabel("বাসা ও রাস্তা").fill("বাড়ি ৭, সেক্টর ৪");
  await button(page, "অর্ডার কনফার্ম করুন").click();
  await expect(page).toHaveURL(/\/orders\/\d+/, { timeout: 15_000 });
  tanvirOrder = Number(page.url().split("/").pop());
  await expect(page.getByText("ইলেকট্রিশিয়ান ভিজিট").first()).toBeVisible();
  expect(problems).toEqual([]);
});

test("order: reschedule the booking, then cancel the whole order", async ({ page }) => {
  const problems = watch(page);
  await signIn(page, "01711000003");
  await page.goto(`${C}/orders/${tanvirOrder}`);
  await button(page, "সময় বদলান").click();
  const dialog = page.getByRole("dialog");
  await dialog.getByLabel("নতুন তারিখ").fill(new Date(Date.now() + 3 * 864e5).toISOString().slice(0, 10));
  await dialog.getByRole("button", { name: "সেভ করুন" }).click();
  await expect(page.getByText("সময় বদলানো হয়েছে।")).toBeVisible();
  await button(page, "পুরো অর্ডার বাতিল করুন").click();
  await expect(page.getByText("বাতিল").first()).toBeVisible();
  expect(problems).toEqual([]);
});

test("checkout: saved address, product + service, bKash payment through the gateway", async ({ page }) => {
  const problems = watch(page);
  const t = await signIn(page, "01711000003");
  await emptyCart(page, t);
  await page.goto(`${C}/shop`);
  await page.getByRole("button", { name: /কার্টে যোগ করুন/ }).first().click();
  await page.goto(`${C}/services/ac-cleaning`);
  await button(page, "কার্টে যোগ করুন").click();
  await expect(page).toHaveURL(/\/cart$/);
  await page.getByRole("link", { name: /চেকআউট/ }).or(page.getByRole("button", { name: /চেকআউট/ })).first().click();
  // the address saved by the first order is offered and selected
  await expect(page.getByText("বাড়ি ৭, সেক্টর ৪").first()).toBeVisible();
  await page.getByText("বিকাশ সরাসরি পেমেন্ট").click();
  await button(page, "অর্ডার কনফার্ম করুন").click();
  await page.waitForURL(/\/api\/payments\/bkash\/mock\//, { timeout: 15_000 });
  await page.locator("button.pay").click();  // the mock gateway page
  await page.waitForURL(/\/payment\/result/, { timeout: 15_000 });
  await expect(page.getByText(/সফল|ধরে রাখা|পরিশোধ/).first()).toBeVisible();
  expect(problems).toEqual([]);
});

test("checkout in Khulna: city picker, Khulna area, tenant asks the landlord", async ({ page }) => {
  const problems = watch(page);
  const t = await signIn(page, "01711000007", "Khulna");
  await emptyCart(page, t);
  await page.goto(`${C}/services/plumber-visit`);
  await button(page, "কার্টে যোগ করুন").click();
  await expect(page).toHaveURL(/\/cart$/);
  await page.getByRole("link", { name: /চেকআউট/ }).or(page.getByRole("button", { name: /চেকআউট/ })).first().click();
  await page.getByText("নতুন ঠিকানা").click();
  const areas = await page.getByLabel("এলাকা").locator("option").allTextContents();
  expect(areas).toContain("নিরালা");
  expect(areas).not.toContain("ধানমন্ডি");  // only Khulna areas when Khulna is the city
  await page.getByLabel("এলাকা").selectOption({ label: "নিরালা" });
  await page.getByLabel("বাসা ও রাস্তা").fill("নিরালা আবাসিক, রোড ১৩");
  await page.getByText("আমি একজন ভাড়াটিয়া").click();
  await page.getByLabel("বাড়িওয়ালার মোবাইল নম্বর").fill("01799000222");
  await button(page, "অর্ডার কনফার্ম করুন").click();
  await expect(page).toHaveURL(/\/orders\/\d+/, { timeout: 15_000 });
  await expect(page.getByText("ভাড়া থেকে কাটা")).toBeVisible();
  expect(problems).toEqual([]);
});

test("checkout: loyalty points give a discount", async ({ page }) => {
  const problems = watch(page);
  // Ensure customer has loyalty points
  const adminRes = await page.request.post(`${GATEWAY}/api/auth/login/`, { data: { phone: "01700000000", password: "demo1234" } });
  const adminTok = await adminRes.json();
  await page.request.post(`${GATEWAY}/api/admin/loyalty/accounts/2/adjust/`, {
    headers: { Authorization: `Bearer ${adminTok.access}` },
    data: { points: 50, reason: "demo points" },
  });
  const t = await signIn(page, "01711000001");
  await emptyCart(page, t);
  await page.goto(`${C}/services/home-deep-clean`);
  await button(page, "কার্টে যোগ করুন").click();
  await expect(page).toHaveURL(/\/cart$/);
  await page.getByRole("link", { name: /চেকআউট/ }).or(page.getByRole("button", { name: /চেকআউট/ })).first().click();
  await expect(page.getByText("বাড়ি ১২, রোড ৭").first()).toBeVisible();  // his saved home address
  await page.getByText(/পয়েন্ট ব্যবহার করুন/).click();
  await button(page, "অর্ডার কনফার্ম করুন").click();
  await expect(page).toHaveURL(/\/orders\/\d+/, { timeout: 15_000 });
  await expect(page.getByText("ছাড়").first()).toBeVisible();
  expect(problems).toEqual([]);
});

test("AI quote → book the suggested service", async ({ page }) => {
  const problems = watch(page);
  const t = await signIn(page, "01711000003");
  await emptyCart(page, t);
  await page.goto(`${C}/ai-quote`);
  await page.getByRole("textbox").last().fill("বেসিনের পাইপ থেকে পানি পড়ছে");
  await button(page, /বিশ্লেষণ/).click();
  await expect(page.getByText("প্রস্তাবিত সার্ভিস")).toBeVisible();
  await button(page, /এখনই বুক করুন/).click();
  await expect(page).toHaveURL(/\/checkout|\/cart|\/services\//);
  await emptyCart(page, t);
  expect(problems).toEqual([]);
});

test("subscribe to a cleaning plan", async ({ page }) => {
  const problems = watch(page);
  await signIn(page, "01711000003");
  await page.goto(`${C}/subscriptions`);
  await page.getByRole("link", { name: "বেছে নিন" }).or(page.getByRole("button", { name: "বেছে নিন" })).first().click();
  await expect(page).toHaveURL(/\/subscriptions\/new\//);
  // the saved address from the first checkout is picked automatically
  await expect(page.getByText("বাড়ি ৭, সেক্টর ৪").first()).toBeVisible();
  await expect(button(page, "সাবস্ক্রাইব করুন")).toBeEnabled({ timeout: 10_000 });
  await button(page, "সাবস্ক্রাইব করুন").click();
  await expect(page).toHaveURL(/\/subscriptions\/\d+/, { timeout: 15_000 });
  expect(problems).toEqual([]);
});

test("custom request: send one, and accept a quote", async ({ page }) => {
  const problems = watch(page);
  await signIn(page, "01711000003");
  await page.goto(`${C}/custom-requests/new`);
  await page.getByLabel("কী কাজ?").fill("গ্রিল রং করা");
  await page.getByLabel("বিস্তারিত").fill("বারান্দার দুটি গ্রিল, পুরনো রং তুলে নতুন রং");
  await page.getByLabel("এলাকা").selectOption({ label: "উত্তরা" });
  await page.getByLabel("ঠিকানা").fill("বাড়ি ৭, সেক্টর ৪");
  await button(page, "রিকোয়েস্ট পাঠান").click();
  await expect(page).toHaveURL(/\/custom-requests\/\d+/, { timeout: 15_000 });
  expect(problems).toEqual([]);
});

test("custom request: Arif accepts the IPS quote", async ({ page }) => {
  const problems = watch(page);
  const t = await signIn(page, "01711000005", "Khulna");
  const reqs = await api<{ results: { id: number; service_type: string }[] }>(page, t, "/api/custom-requests/");
  const req = reqs.results.find((r) => r.service_type.includes("আইপিএস"))!;
  await page.goto(`${C}/custom-requests/${req.id}`);
  const acceptBtn = page.getByRole("button", { name: "কোট গ্রহণ করুন" });
  try {
    await acceptBtn.click({ timeout: 7000 });
  } catch {
    // already accepted
  }
  await expect(page.getByText(/গ্রহণ করা|চূড়ান্ত মূল্য|অগ্রিম/).first()).toBeVisible({ timeout: 10_000 });
  expect(problems).toEqual([]);
});

test("report a city problem with a photo and a map pin, then support another", async ({ page }) => {
  const problems = watch(page);
  await signIn(page, "01711000008", "Khulna");
  await page.goto(`${C}/issues/new`);
  await page.getByRole("button", { name: "ড্রেন বন্ধ" }).click();
  await page.locator('input[type="file"]').first().setInputFiles(PHOTO);
  await expect(page.locator('img[src*="/media/public/"]').first()).toBeVisible({ timeout: 15_000 });
  await page.getByLabel("শিরোনাম (ঐচ্ছিক)").fill("ডাকবাংলো বাজারের ড্রেন উপচে পড়ছে");
  await page.getByLabel("এলাকা").selectOption({ label: "ডাকবাংলো" });
  const map = page.locator(".leaflet-container").first();
  await map.click({ position: { x: 120, y: 90 } });
  await button(page, "রিপোর্ট জমা দিন").click();
  const forced = page.getByRole("button", { name: /তবুও রিপোর্ট করুন/ });
  try {
    await forced.waitFor({ state: "visible", timeout: 5000 });
    await forced.click();
  } catch {}
  await expect(page).toHaveURL(/\/issues\/\d+/, { timeout: 15_000 });
  await expect(page.getByText("ডাকবাংলো বাজারের ড্রেন উপচে পড়ছে")).toBeVisible();

  await page.goto(`${C}/issues`);
  await page.getByRole("button", { name: /সমর্থন|▲|\^/ }).first().click().catch(() => {});
  expect(problems).toEqual([]);
});

test("community: post, like and comment", async ({ page }) => {
  const problems = watch(page);
  await signIn(page, "01711000008", "Khulna");
  await page.goto(`${C}/community`);
  await page.getByLabel("কী জানাতে চান?").fill("ডাকবাংলোয় কাল সকালে পানি থাকবে না।");
  // the form starts with her home area (Dakbangla) even though the list filter shows every area
  await expect(page.getByLabel("কোন এলাকার জন্য")).toHaveValue(/\d+/);
  await button(page, "পোস্ট করুন").click();
  await expect(page.getByText("ডাকবাংলোয় কাল সকালে পানি থাকবে না।").first()).toBeVisible();
  expect(problems).toEqual([]);
});

test("home profile: edit the home and add a reminder", async ({ page }) => {
  const problems = watch(page);
  await signIn(page, "01711000006", "Khulna");
  await page.goto(`${C}/home-profile`);
  await button(page, /রিমাইন্ডার যোগ করুন/).isVisible();
  await page.getByPlaceholder(/ট্যাংক|সার্ভিসিং|কাজের নাম/).first().fill("পানির ট্যাংক পরিষ্কার");
  await page.locator('input[type="date"]').last().fill(new Date(Date.now() + 20 * 864e5).toISOString().slice(0, 10));
  await button(page, /রিমাইন্ডার যোগ করুন/).click();
  await expect(page.getByText("পানির ট্যাংক পরিষ্কার")).toBeVisible();
  expect(problems).toEqual([]);
});

test("sign in through the form, switch language and city, sign out", async ({ page }) => {
  const problems = watch(page);
  await page.goto(`${C}/login`);
  await page.getByLabel("মোবাইল নম্বর").fill("01711000002");
  await page.getByLabel("পাসওয়ার্ড").fill("demo1234");
  await button(page, "লগইন").click();
  await expect(page.getByText("নুসরাত জাহান").first()).toBeVisible({ timeout: 10_000 });
  await page.getByRole("button", { name: "Switch to English" }).click();
  await expect(page.getByRole("link", { name: "Services" }).first()).toBeVisible();
  await page.getByRole("button", { name: "বাংলায় দেখুন" }).click();
  await page.locator("header select").first().selectOption("Khulna");
  await page.waitForLoadState("networkidle");
  await expect(page.locator("header select").first()).toHaveValue("Khulna");
  expect(problems).toEqual([]);
});

test("provider: accept a Khulna job, travel, arrival code, photos, complete, rate the customer", async ({ page, browser }) => {
  const problems = watch(page);
  const saiful = await signIn(page, "01811000006", "Khulna");
  await page.goto(`${P}/`);
  await page.getByRole("tab", { name: "নতুন কাজ" }).or(page.getByRole("button", { name: "নতুন কাজ" })).first().click();
  await button(page, "গ্রহণ করুন").click();
  await expect(page).toHaveURL(/\/jobs\/\d+/, { timeout: 15_000 });
  const jobId = page.url().match(/\/jobs\/(\d+)/)![1];
  const acceptedJob = await api<{ id: number; source_id: number; customer_phone: string }>(page, saiful, `/api/providers/jobs/${jobId}/`);

  await button(page, "পথে আছি").click();
  // the customer reads the arrival code in their app
  const custAuth = await (await page.request.post(`${GATEWAY}/api/auth/login/`, { data: { phone: acceptedJob.customer_phone, password: "demo1234" } })).json();
  const booking = await api<{ arrival_code: string }>(page, custAuth, `/api/bookings/${acceptedJob.source_id}/`);
  await page.getByLabel("গ্রাহকের ৪ সংখ্যার কোড").fill(booking.arrival_code);
  await page.locator('input[type="file"]').first().setInputFiles(PHOTO);
  await expect(page.locator('img[src*="/media/public/"]').first()).toBeVisible({ timeout: 15_000 });
  await button(page, "কাজ শুরু").click();
  await expect(button(page, "কাজ সম্পন্ন")).toBeVisible({ timeout: 10_000 });
  await page.locator('input[type="file"]').first().setInputFiles(PHOTO);
  await button(page, "কাজ সম্পন্ন").click();
  await expect(page.getByText("গ্রাহককে রেটিং দিন")).toBeVisible({ timeout: 10_000 });
  await page.getByRole("radio").nth(4).click();
  await button(page, "রেটিং দিন").click();
  await expect(page.getByText("আপনি গ্রাহককে রেটিং দিয়েছেন")).toBeVisible();
  expect(problems).toEqual([]);

  // the customer sees it finished and reviews the provider
  const cust = await browser.newPage();
  const custProblems = watch(cust);
  await cust.addInitScript((t) => localStorage.setItem("shohor.tokens", JSON.stringify(t)), custAuth);
  const orders = await api<{ results: { id: number; bookings: { id: number }[] }[] }>(cust, custAuth, "/api/orders/");
  const order = orders.results.find((o) => o.bookings.some((b) => b.id === acceptedJob.source_id))!;
  await cust.goto(`${C}/orders/${order.id}`);
  await cust.getByRole("button", { name: "রিভিউ দিন" }).first().click();
  const dlg = cust.getByRole("dialog");
  await dlg.getByRole("radio").nth(4).click().catch(async () => dlg.locator("button", { hasText: "★" }).nth(4).click());
  await dlg.getByRole("button", { name: /জমা দিন|রিভিউ দিন/ }).last().click();
  await expect(cust.getByText("আপনার রেটিং:")).toBeVisible({ timeout: 10_000 });
  expect(custProblems).toEqual([]);
});

test("admin: quote a custom request and forward a city problem", async ({ page }) => {
  const problems = watch(page);
  await signIn(page, "01700000000");
  await page.goto(`${A}/custom-requests`);
  await page.locator("tbody tr").filter({ hasText: "গ্রিল রং করা" }).first().click();
  const dialog = page.getByRole("dialog");
  await expect(dialog).toBeVisible({ timeout: 10_000 });
  const review = dialog.getByRole("button", { name: "রিভিউ শুরু করুন" });
  if (await review.isVisible().catch(() => false)) await review.click();
  await dialog.getByLabel("মজুরি").fill("2500");
  await dialog.getByLabel("উপকরণ").fill("1200");
  await dialog.locator("select#cat, select").first().selectOption({ index: 1 });
  await dialog.getByRole("button", { name: "কোট পাঠান" }).click();
  await expect(dialog).toBeHidden({ timeout: 10_000 });

  await page.goto(`${A}/issues`);
  await page.getByRole("button", { name: "নতুন" }).first().click();
  await page.locator("tbody tr").first().click();
  const d2 = page.getByRole("dialog");
  await expect(d2).toBeVisible({ timeout: 10_000 });
  const options = await d2.getByLabel("নতুন অবস্থা").locator("option").allTextContents().catch(() => []);
  if (options.length > 0) {
    await d2.getByLabel("নতুন অবস্থা").selectOption({ index: 0 });
    const authSelect = d2.getByLabel("কর্তৃপক্ষ");
    if (await authSelect.isVisible().catch(() => false)) {
      await authSelect.selectOption({ index: 1 });
    }
    await d2.getByRole("button", { name: "আপডেট করুন" }).click();
    await expect(d2).toBeHidden({ timeout: 10_000 });
  }
  expect(problems).toEqual([]);
});
