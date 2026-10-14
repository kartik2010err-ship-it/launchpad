// Writes data: creates one account and one project per run. Run against
// local or preview deployments, not production.
import { BASE, check as step, finish, launch } from "./lib.mjs";
const browser = await launch();
const ctx = await browser.newContext({ viewport: { width: 390, height: 844 } });
const page = await ctx.newPage();
const errors = [];
page.on("pageerror", (e) => errors.push(e.message));
page.on("response", (r) => { if (r.url().includes("/api/") && r.status() >= 500) errors.push(`HTTP ${r.status()} ${r.url()}`); });
const email = `flow.${Date.now()}@Example.edu`;

// 1. Deep link while signed out returns there after sign-up
await page.goto(`${BASE}/projects/new`);
await page.waitForURL(/sign-in/, { timeout: 5000 }).catch(() => {});
step("signed-out deep link goes to sign-in with next", page.url().includes("/sign-in?next=%2Fprojects%2Fnew"), page.url());
await page.getByRole("tab", { name: "Create an account" }).click();
await page.getByLabel("Your name").fill("Flow Tester");
await page.getByLabel("Email").fill(email);
await page.getByLabel("Password").fill("flowpass123");
await page.getByLabel("Password").press("Enter");
await page.waitForURL(/\/projects\/new/, { timeout: 10000 }).catch(() => {});
step("sign-up via Enter lands on the deep-linked page", page.url().endsWith("/projects/new"), page.url());

// 2. Create a project and run the interview
await page.getByLabel("Project title or rough topic").fill("Salt and plant growth");
await page.getByLabel(/research question/i).fill("Does salt concentration in water affect how tall bean plants grow over three weeks?");
await page.getByRole("button", { name: "Start the interview" }).click();
await page.waitForURL(/\/projects\/\d+/, { timeout: 10000 });
const projectUrl = page.url();
step("project created", /\/projects\/\d+/.test(projectUrl), projectUrl);
const pid = projectUrl.match(/projects\/(\d+)/)[1];
await page.goto(`${BASE}/projects/${pid}/interview`);
await page.waitForLoadState("networkidle");
const boxes = page.locator("textarea");
const n = await boxes.count();
for (let i = 0; i < n; i++) await boxes.nth(i).fill("I will measure plant height in centimetres every two days, with five plants per salt level (0, 1, 2, 4 g/L), and a no-salt control group kept in the same light.");
await page.getByRole("button", { name: "Submit answers" }).click();
await page.waitForLoadState("networkidle");
step("interview answers submitted", n > 0 && errors.length === 0, `${n} answers`);
const evalBtn = page.getByRole("button", { name: /Evaluate/ }).first();
await evalBtn.click();
await page.waitForLoadState("networkidle");
await page.goto(`${BASE}/projects/${pid}/analysis`);
await page.waitForLoadState("networkidle");
const hasScore = /\b\d{1,3}\b/.test(await page.locator("main, .main, #root").first().innerText());
step("evaluation renders on analysis page", hasScore && errors.length === 0);

// 3. Survives reload
await page.reload();
await page.waitForLoadState("networkidle");
step("still signed in after reload", page.url().includes(`/projects/${pid}`), page.url());

// 4. Expired session mid-use redirects to sign-in and back
await page.evaluate(() => localStorage.setItem("research-coach-token", "forged.token"));
await page.goto(`${BASE}/projects/${pid}/rubric`);
await page.waitForURL(/sign-in/, { timeout: 10000 }).catch(() => {});
step("invalid token -> sign-in with next", page.url().includes(`next=%2Fprojects%2F${pid}%2Frubric`), page.url());
await page.getByLabel("Email").fill(email.toLowerCase());
await page.getByLabel("Password").fill("flowpass123");
await page.getByRole("button", { name: "Sign in" }).last().click();
await page.waitForURL(new RegExp(`/projects/${pid}/rubric`), { timeout: 10000 }).catch(() => {});
step("sign back in (lowercased email) returns to the page", page.url().endsWith(`/projects/${pid}/rubric`), page.url());

// 5. Wrong password shows a readable error
const ctx2 = await browser.newContext();
const p2 = await ctx2.newPage();
await p2.goto(`${BASE}/sign-in`);
await p2.getByLabel("Email").fill("ava@example.edu");
await p2.getByLabel("Password").fill("nope-nope");
await p2.getByLabel("Password").press("Enter");
const alert = await p2.getByRole("alert").innerText({ timeout: 5000 }).catch(() => "");
step("wrong password shows an alert", /incorrect/i.test(alert), JSON.stringify(alert));

// 6. API down while holding a valid session: no silent sign-out
await page.route(/localhost:5173\/api\//, (route) => route.abort("connectionrefused"));
await page.reload();
await page.getByRole("button", { name: "Try again" }).waitFor({ timeout: 15000 }).catch(() => {});
const downText = await page.locator("#root").innerText();
step("server unreachable shows retry screen", /Can't reach Research Coach/.test(downText), JSON.stringify(downText.slice(0, 80)));
const tokenKept = await page.evaluate(() => !!localStorage.getItem("research-coach-token"));
step("token kept during outage", tokenKept);
await page.unroute(/localhost:5173\/api\//);
await page.getByRole("button", { name: "Try again" }).click();
await page.waitForLoadState("networkidle");
step("recovers after outage", page.url().endsWith(`/projects/${pid}/rubric`) && !(await page.locator(".app-state[role=alert]").count()), page.url());

step("no page errors / 5xx during flows", errors.length === 0, errors.join(" | "));
await browser.close();
finish();
