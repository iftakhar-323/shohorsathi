import { defineConfig, devices } from "@playwright/test";

// Browser tests for the three web apps against a running stack (docker compose up; gateway on :8088).
// The dev servers are started here and proxy /api to the gateway.
export default defineConfig({
  testDir: "tests",
  timeout: 45_000,
  retries: 1,
  reporter: [["list"]],
  use: { trace: "retain-on-failure", screenshot: "only-on-failure" },
  projects: [
    { name: "desktop", use: { ...devices["Desktop Chrome"] } },
    { name: "mobile", use: { ...devices["Pixel 7"] }, grep: /@mobile/ },
  ],
  webServer: [
    { command: "pnpm --filter customer-web dev --port 5173 --strictPort", url: "http://localhost:5173", reuseExistingServer: true, cwd: "../.." },
    { command: "pnpm --filter provider-web dev --port 5174 --strictPort", url: "http://localhost:5174", reuseExistingServer: true, cwd: "../.." },
    { command: "pnpm --filter admin-web dev --port 5175 --strictPort", url: "http://localhost:5175", reuseExistingServer: true, cwd: "../.." },
  ],
});
