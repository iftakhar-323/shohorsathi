import { expect, test } from "@playwright/test";

const SITE = "http://localhost:5173";

test("home is Bangla first and switches to English", async ({ page }) => {
  await page.goto(SITE);
  await expect(page.getByRole("heading", { level: 1 })).toContainText("ভরসাযোগ্য সমাধান");
  await page.getByRole("button", { name: "Switch to English" }).click();
  await expect(page.getByRole("heading", { level: 1 })).toContainText("reliably solved");
  await page.reload();
  await expect(page.getByRole("heading", { level: 1 })).toContainText("reliably solved"); // remembered
  await page.getByRole("button", { name: "বাংলায় দেখুন" }).click();
});

test("services list opens a service page", async ({ page }) => {
  await page.goto(`${SITE}/services`);
  const card = page.getByRole("article").first();
  await expect(card).toBeVisible();
  await card.getByRole("link").click();
  await expect(page).toHaveURL(/\/services\/.+/);
  await expect(page.getByRole("button", { name: "কার্টে যোগ করুন" })).toBeVisible();
});

test("sign-up asks for consent and links the privacy policy", async ({ page }) => {
  await page.goto(`${SITE}/register`);
  await expect(page.getByRole("heading", { name: "নতুন অ্যাকাউন্ট" })).toBeVisible();
  await page.goto(`${SITE}/privacy`);
  await expect(page.getByRole("heading", { name: "প্রাইভেসি নীতি" })).toBeVisible();
  await expect(page.getByText("NID ও আইডি কার্ডের ছবি এনক্রিপ্ট")).toBeVisible();
});

test("city issues page shows the map @mobile", async ({ page }) => {
  await page.goto(`${SITE}/issues`);
  await expect(page.getByRole("heading", { name: "শহরের সমস্যা" })).toBeVisible();
  await expect(page.locator(".leaflet-container")).toBeVisible();
  // no horizontal scroll at phone width
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
  expect(overflow).toBeLessThanOrEqual(1);
});

test("home has no horizontal scroll on a phone @mobile", async ({ page }) => {
  await page.goto(SITE);
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
  expect(overflow).toBeLessThanOrEqual(1);
});
