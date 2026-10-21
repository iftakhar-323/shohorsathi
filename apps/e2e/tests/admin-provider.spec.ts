import { expect, test } from "@playwright/test";

import { ADMIN, signIn } from "./helpers";

test("admin dashboard and provider verification load", async ({ page }) => {
  test.skip(!ADMIN.phone, "set E2E_ADMIN_PHONE / E2E_ADMIN_PASSWORD");
  await signIn(page, ADMIN.phone, ADMIN.password);
  await page.goto("http://localhost:5175/");
  await expect(page.getByRole("heading", { name: "আজকের অবস্থা" })).toBeVisible();
  await page.getByRole("link", { name: "প্রোভাইডার যাচাই" }).click();
  await expect(page.getByRole("heading", { name: "প্রোভাইডার যাচাই" })).toBeVisible();
  await page.getByRole("link", { name: "অ্যানালিটিক্স" }).click();
  await expect(page.locator(".leaflet-container")).toBeVisible();
});

test("customers cannot use the admin app", async ({ page }) => {
  await page.goto("http://localhost:5175/");
  await expect(page).toHaveURL(/\/login/);
  await expect(page.getByRole("button", { name: "নতুন অ্যাকাউন্ট খুলুন" })).toHaveCount(0); // admins are not self-registered
});

test("provider portal shows its login", async ({ page }) => {
  await page.goto("http://localhost:5174/");
  await expect(page).toHaveURL(/\/login/);
  await expect(page.getByText("শহরসাথী পার্টনার")).toBeVisible();
});
