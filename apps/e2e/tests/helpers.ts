import type { Page } from "@playwright/test";

const GATEWAY = process.env.GATEWAY_URL ?? "http://localhost:8088";

/** Log in through the API and put the tokens where the apps keep them, so tests start signed in. */
export async function signIn(page: Page, phone: string, password: string) {
  const res = await page.request.post(`${GATEWAY}/api/auth/login/`, { data: { phone, password } });
  if (!res.ok()) throw new Error(`login failed for ${phone}: ${res.status()}`);
  const tokens = await res.json();
  await page.addInitScript((t) => localStorage.setItem("shohor.tokens", JSON.stringify(t)), tokens);
}

export const ADMIN = { phone: process.env.E2E_ADMIN_PHONE ?? "", password: process.env.E2E_ADMIN_PASSWORD ?? "" };
