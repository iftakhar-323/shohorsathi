// Fails when a Bangla UI string has no English translation in src/i18n/en.ts.
// Run from the repo root: node packages/web-core/scripts/check-i18n.mjs
import { readFileSync, readdirSync, statSync } from "node:fs";
import { join } from "node:path";

const ROOTS = ["packages/web-core/src", "apps/customer-web/src", "apps/provider-web/src", "apps/admin-web/src"];
const DICT = "packages/web-core/src/i18n/en.ts";
const BANGLA = /[ঀ-৿]/;

function files(dir) {
  return readdirSync(dir).flatMap((name) => {
    const path = join(dir, name);
    return statSync(path).isDirectory() ? files(path) : /\.tsx?$/.test(name) ? [path] : [];
  });
}

const dict = new Set();
for (const m of readFileSync(DICT, "utf8").matchAll(/^ {2}("(?:[^"\\]|\\.)*"):/gm)) dict.add(JSON.parse(m[1]));

const missing = [];
const unwrapped = [];
for (const file of ROOTS.flatMap(files)) {
  if (file.endsWith("i18n/en.ts") || file.endsWith("lib/i18n.tsx")) continue;
  const src = readFileSync(file, "utf8");
  for (const m of src.matchAll(/"((?:[^"\\\n]|\\.)*)"/g)) {
    const text = JSON.parse(`"${m[1]}"`);
    if (BANGLA.test(text) && !dict.has(text)) missing.push(`${file}: ${text}`);
  }
  // Bangla outside quotes is JSX text that skipped t()
  const stripped = src.replace(/"(?:[^"\\\n]|\\.)*"/g, '""').replace(/\/\/.*$/gm, "").replace(/`[^`]*`/g, "``");
  stripped.split("\n").forEach((line, i) => {
    if (BANGLA.test(line)) unwrapped.push(`${file}:${i + 1}: ${line.trim()}`);
  });
}

if (missing.length || unwrapped.length) {
  if (missing.length) console.error(`Missing English translations (${missing.length}):\n  ` + missing.join("\n  "));
  if (unwrapped.length) console.error(`Bangla text not wrapped in t() (${unwrapped.length}):\n  ` + unwrapped.join("\n  "));
  process.exit(1);
}
console.log(`i18n OK: ${dict.size} strings translated`);
