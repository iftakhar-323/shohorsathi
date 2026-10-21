import { expect, test } from "@playwright/test";

import { ADMIN, signIn } from "./helpers";

const CUSTOMER_SITE = "http://localhost:5173";
const PROVIDER_SITE = "http://localhost:5174";
const ADMIN_SITE = "http://localhost:5175";

test("customer service page shows female provider preference option", async ({ page }) => {
  await page.goto(`${CUSTOMER_SITE}/services`);
  const card = page.getByRole("article").first();
  await expect(card).toBeVisible();
  await card.getByRole("link").click();
  await expect(page).toHaveURL(/\/services\/.+/);
  await expect(page.getByText("মহিলা প্রোভাইডার চাই")).toBeVisible();
});

test("public live tracking page renders expired state gracefully", async ({ page }) => {
  await page.goto(`${CUSTOMER_SITE}/track/sample-expired-token`);
  await expect(page.getByText("এই লিংকের মেয়াদ শেষ।")).toBeVisible();
});

test("provider portal redirects unauthenticated user to login", async ({ page }) => {
  await page.goto(`${PROVIDER_SITE}/training`);
  await expect(page).toHaveURL(/\/login/);
  await page.goto(`${PROVIDER_SITE}/insurance`);
  await expect(page).toHaveURL(/\/login/);
});

test("admin trust and safety pages load with their tabs", async ({ page }) => {
  test.skip(!ADMIN.phone, "set E2E_ADMIN_PHONE / E2E_ADMIN_PASSWORD");
  await signIn(page, ADMIN.phone, ADMIN.password);

  // Safety & Trust page
  await page.goto(`${ADMIN_SITE}/safety`);
  await expect(page.getByRole("heading", { name: "সেফটি ও ট্রাস্ট" })).toBeVisible();
  await expect(page.getByRole("tab", { name: "জরুরি SOS অ্যালার্ট" })).toBeVisible();
  await expect(page.getByRole("tab", { name: "রিভিউ আপত্তি" })).toBeVisible();

  // Insurance page
  await page.goto(`${ADMIN_SITE}/insurance`);
  await expect(page.getByRole("heading", { name: "সুরক্ষা বিমা" })).toBeVisible();
  await expect(page.getByRole("tab", { name: "বিমা ক্লেইমসমূহ" })).toBeVisible();
  await expect(page.getByRole("tab", { name: "বিমা প্ল্যানসমূহ" })).toBeVisible();

  // Training editor page
  await page.goto(`${ADMIN_SITE}/training`);
  await expect(page.getByRole("heading", { name: "ট্রেনিং মডিউল এডিটর" })).toBeVisible();
});
