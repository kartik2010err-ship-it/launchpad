// Shared setup for the browser checks. Point E2E_BASE_URL at any deployment:
//   E2E_BASE_URL=https://researchcoach.app npm run smoke
import { chromium } from "playwright";

export const BASE = (process.env.E2E_BASE_URL ?? "http://localhost:5173").replace(/\/$/, "");
export const DEMO_PASSWORD = "coach1234";

export function launch() {
  // CHROMIUM_PATH lets a machine with a preinstalled browser skip the download.
  return chromium.launch(process.env.CHROMIUM_PATH ? { executablePath: process.env.CHROMIUM_PATH } : {});
}

export async function apiLogin(email, password = DEMO_PASSWORD) {
  const response = await fetch(`${BASE}/api/auth/login`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
  if (!response.ok) throw new Error(`login ${email}: ${response.status}`);
  return (await response.json()).access_token;
}

export async function apiGet(path, token) {
  const response = await fetch(`${BASE}/api${path}`, { headers: { Authorization: `Bearer ${token}` } });
  return response.ok ? response.json() : null;
}

let failures = 0;
export function check(name, ok, detail = "") {
  if (!ok) failures += 1;
  console.log(`${ok ? "PASS" : "FAIL"}  ${name}${detail ? `  ${detail}` : ""}`);
}
export function finish() {
  console.log(failures ? `\n${failures} check(s) failed` : "\nAll checks passed");
  process.exit(failures ? 1 : 0);
}
