// report-out/report.html → report-out/ShohorSathi-website-Khulna.pdf (A4, page numbers). Run from the repo root.
import { createRequire } from "node:module";
import path from "node:path";

const ROOT = path.resolve(path.dirname(new URL(import.meta.url).pathname), "../..");
const require = createRequire(path.join(ROOT, "apps/e2e/package.json"));
const { chromium } = require("@playwright/test");
const out = path.join(ROOT, "report-out");
const browser = await chromium.launch();
const page = await browser.newPage();
await page.goto(`file://${out}/report.html`, { waitUntil: "networkidle" });
await page.evaluate(() => document.fonts.ready);
await page.pdf({
  path: `${out}/ShohorSathi-website-Khulna.pdf`, format: "A4", printBackground: true, preferCSSPageSize: true, displayHeaderFooter: true,
  headerTemplate: "<span></span>",
  footerTemplate: '<div style="width:100%;font-size:8px;color:#7a8a80;padding:0 13mm;display:flex;justify-content:space-between"><span>ShohorSathi — website walkthrough, Khulna focus</span><span><span class="pageNumber"></span> / <span class="totalPages"></span></span></div>',
});
await browser.close();
console.log("pdf written");
