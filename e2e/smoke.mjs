// Read-only: signs in as demo accounts and opens every page, failing on page
// crashes, 5xx responses, sideways scrolling on a phone, or pages stuck loading.
// Safe to run against production.
import { BASE, DEMO_PASSWORD, apiGet, apiLogin, check, finish, launch } from "./lib.mjs";

const USERS = (process.env.E2E_USERS ?? "ava@example.edu,mentor@example.edu,jordan@example.edu").split(",");
const VIEWPORTS = { desktop: { width: 1366, height: 900 }, phone: { width: 390, height: 844 } };

async function routesFor(token) {
  const projects = (await apiGet("/projects", token)) ?? [];
  const workspaces = (await apiGet("/workspaces", token)) ?? [];
  let workspaceId = workspaces[0]?.id;
  let teamId;
  for (const workspace of workspaces) {
    const teams = await apiGet(`/workspaces/${workspace.id}/teams`, token);
    if (teams?.length) {
      workspaceId = workspace.id;
      teamId = teams[0].id;
      break;
    }
  }
  const projectId = (projects.find((p) => p.workspace_id === workspaceId) ?? projects[0])?.id;
  const routes = ["/home", "/projects", "/projects/new", "/workspaces/new", "/workspaces/join", "/library",
    "/winning-projects", "/outreach", "/assistant", "/isef"];
  if (workspaceId) {
    routes.push(...["", "/projects", "/teams", "/members", "/activity", "/settings"].map((s) => `/workspaces/${workspaceId}${s}`));
    if (teamId) routes.push(`/workspaces/${workspaceId}/teams/${teamId}`);
    if (projectId) routes.push(`/workspaces/${workspaceId}/projects/${projectId}`);
  }
  if (projectId) {
    routes.push(...["", "/interview", "/analysis", "/rubric", "/novelty", "/refine", "/plan", "/timeline", "/poster",
      "/judging", "/notebook", "/assistant"].map((s) => `/projects/${projectId}${s}`));
  }
  return routes;
}

const browser = await launch();
for (const [label, viewport] of Object.entries(VIEWPORTS)) {
  for (const email of USERS) {
    const token = await apiLogin(email);
    const routes = await routesFor(token);
    const context = await browser.newContext({ viewport });
    const page = await context.newPage();
    let problems = [];
    page.on("pageerror", (e) => problems.push(`crash: ${e.message}`));
    page.on("response", (r) => {
      if (r.url().includes("/api/") && r.status() >= 500) problems.push(`HTTP ${r.status()} ${new URL(r.url()).pathname}`);
    });

    await page.goto(`${BASE}/sign-in`);
    await page.getByLabel("Email").fill(email);
    await page.getByLabel("Password").fill(DEMO_PASSWORD);
    await page.getByLabel("Password").press("Enter");
    await page.waitForURL(/\/home/, { timeout: 20000 }).catch(() => {});
    check(`[${label}] ${email} signs in`, page.url().endsWith("/home"), page.url());

    for (const route of routes) {
      problems = [];
      await page.goto(BASE + route);
      await page.waitForLoadState("networkidle").catch(() => {});
      const state = await page.evaluate(() => ({
        overflow: document.documentElement.scrollWidth - window.innerWidth,
        loading: /Loading…/.test(document.body.innerText),
        crashed: !!document.querySelector(".app-state[role=alert]"),
      }));
      if (state.overflow > 2) problems.push(`scrolls sideways by ${state.overflow}px`);
      if (state.loading) problems.push("stuck loading");
      if (state.crashed) problems.push("error screen shown");
      check(`[${label}] ${email} ${route}`, problems.length === 0, [...new Set(problems)].join(" | "));
    }
    await context.close();
  }
}
await browser.close();
finish();
