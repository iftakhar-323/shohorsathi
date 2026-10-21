import { expect, test } from "@playwright/test";

const CUSTOMER_SITE = "http://localhost:5173";

test("customer site serves PWA manifest link and meta tag", async ({ page }) => {
  await page.goto(`${CUSTOMER_SITE}/`);
  const manifest = page.locator('link[rel="manifest"]');
  await expect(manifest).toHaveAttribute("href", "/manifest.webmanifest");
  const themeColor = page.locator('meta[name="theme-color"]');
  await expect(themeColor).toHaveAttribute("content", "#17784A");
});

test("customer header has low-data mode toggle", async ({ page }) => {
  await page.goto(`${CUSTOMER_SITE}/`);
  const lowDataBtn = page.getByRole("button", { name: /লো-ডাটা/i });
  await expect(lowDataBtn).toBeVisible();
  await lowDataBtn.click();
  await expect(page.getByRole("button", { name: /লো-ডাটা চালু/i })).toBeVisible();
});

test("customer registration page offers WhatsApp OTP delivery option", async ({ page }) => {
  await page.goto(`${CUSTOMER_SITE}/register`);
  await expect(page.getByLabel(/WhatsApp/i)).toBeVisible();
  await expect(page.getByLabel(/SMS/i)).toBeVisible();
});
