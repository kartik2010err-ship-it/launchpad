# Deploying and running Research Coach

Research Coach runs as **one Vercel project** (the React frontend plus the
FastAPI backend as a Python serverless function) and **one hosted Postgres
database** (Neon recommended). Both are on free tiers. Nothing runs all the
time, so there is no server to pay for or keep awake.

```
browser ──► researchcoach.app ──► Vercel
                                   ├─ /            static React build (frontend/dist)
                                   └─ /api/*       Python function (api/index.py → backend/app)
                                                      └─► Neon Postgres (DATABASE_URL)
```

Frontend and API share one origin, so there is no CORS to configure and no API
URL baked into the frontend.

---

## What it costs

| Piece | Plan | Monthly cost | Limits that matter |
|---|---|---|---|
| Vercel | Hobby | $0 | 1M function invocations, 4 h active CPU, 360 GB-h memory. Over the limit the project is **paused, never billed**. Hobby is for non-commercial use. |
| Neon | Free | $0 | 0.5 GB storage, 100 compute-hours, scales to zero after 5 min idle. Over the limit compute is **suspended, never billed**. No card required. |
| GitHub Actions | Free | $0 | 2,000 min/month on private repos (unlimited on public). One CI run is ~5 min. |
| Domain | Yearly | ~$1–1.25/mo | The only real cost. See "Custom domain" below. |

**What "free" costs you in speed:** after about 5 minutes with no traffic the
database sleeps and the function instance is recycled. The next request takes
roughly **2–3 seconds** while both wake (about 0.5 s for Neon, 1.5–2.5 s for the
Python cold start). After that, requests take tens of milliseconds. The old
free Render server took 30–60 seconds to wake. The app also retries a read once
by itself and shows "Starting up…" instead of an error while this happens.
Truly always-on compute is not available for free. Don't add keep-alive pings:
they waste your free compute hours and break the spirit of the free-tier terms.

---

## One-time setup

### 1. Create the database (Neon)

1. Sign up at <https://neon.tech> (GitHub login works; no card).
2. Create a project in **AWS US East 2 (Ohio)**. `vercel.json` pins the API
   to Vercel's `cle1` (Cleveland) region next to it. If you ever move the
   database to another region, change `regions` in `vercel.json` to the
   nearest Vercel region, or every query pays a cross-country round trip.
3. On the dashboard, open **Connect**, turn on **Connection pooling**, and copy
   the connection string. Its host ends in `-pooler`, for example
   `postgresql://user:pass@ep-xxx-pooler.us-east-1.aws.neon.tech/neondb?sslmode=require`.
   Paste it as-is; the app fixes the driver prefix itself.

### 2. Point the Vercel project at the repository root

The project used to build from `frontend/`. The backend now lives in the same
project, so the build must start at the repository root.

1. Vercel → your project → **Settings → Build and Deployment → Root Directory**:
   clear it, leaving the repository root, and save.
2. Leave **Framework Preset** as "Other". `vercel.json` supplies the install,
   build and output settings.

### 3. Set environment variables

Vercel → **Settings → Environment Variables**. Set these for **Production**
only:

| Name | Value |
|---|---|
| `DATABASE_URL` | the Neon pooled connection string |
| `SECRET_KEY` | output of `python -c "import secrets; print(secrets.token_urlsafe(48))"`. If the old Render server already had a key of 32+ characters, reuse it so nobody gets signed out. |
| `AI_PROVIDER` | `heuristic` (free). Use `anthropic` only with `ANTHROPIC_API_KEY` set; that is paid per use. |
| `VITE_SITE_URL` | `https://researchcoach.app` once the domain is live (adds a canonical link and sitemap). Leave it unset until then. |

Optional: `SEED_DEMO_DATA=false` stops the demo accounts from being created in
an empty database. `AUTH_RATE_LIMIT` (default 10) sets how many failed
sign-ins each account gets per 5 minutes.

**Do not give Preview deployments the production `DATABASE_URL`.** A preview
build runs whatever code is on its branch, including schema changes, against
whatever database it is given. With no `DATABASE_URL`, previews run on a
throwaway SQLite copy of the demo data, which is what you want for clicking
through a pull request. For a real Postgres preview, create a Neon branch and
set its URL for Preview only.

If production is missing `SECRET_KEY` or `DATABASE_URL`, the API refuses every
request with "The server is not configured yet" instead of running unsafely.
`/api/health` lists exactly what is missing.

### 4. Move the existing data from Render (only if there is data to keep)

Do this before switching traffic. It only reads from the old database.

```bash
# 1. Back up the current database (Render dashboard → the Postgres instance → "External Database URL")
pg_dump --no-owner --no-acl "$OLD_RENDER_DATABASE_URL" > research-coach-backup.sql

# 2. Load it into Neon (use the direct, non-pooler URL for restores)
psql "$NEON_DIRECT_URL" < research-coach-backup.sql

# 3. Check the row counts match
psql "$OLD_RENDER_DATABASE_URL" -c "select count(*) from users"
psql "$NEON_DIRECT_URL"         -c "select count(*) from users"
```

Keep `research-coach-backup.sql` somewhere safe. On its first request the new
deployment adds its two new tables (`app_state`, `rate_limit_hits`) alongside
the existing ones. It never drops or rewrites existing data, and it does not
seed demo data into a database that already has accounts.

If the old backend used SQLite on Render's disk rather than Postgres, its data
did not survive Render's redeploys and restarts, so there is nothing to move.

### 5. Deploy and verify

Merge to `main`; Vercel deploys automatically. Then:

```bash
curl https://<your-domain>/api/health
# {"status":"ok","database":"ok","config_problems":[],"ai_provider":"heuristic","version":"abc1234"}

cd e2e && npm ci && npx playwright install chromium
E2E_BASE_URL=https://<your-domain> npm run smoke   # read-only; safe against production
```

### 6. Retire Render

Once the smoke test passes on the new deployment, delete the Render web
service (and the Render database, after the backup above is verified). That
ends the $7/month charge.

---

## Custom domain

Buy the domain yourself; Research Coach does not depend on any particular
registrar. Then:

1. Vercel → **Settings → Domains → Add** `researchcoach.app`. Also add
   `www.researchcoach.app` and set it to **redirect to** `researchcoach.app`
   (308).
2. Vercel shows the DNS records to create at your registrar: an `A` record for
   the apex (`@`) and a `CNAME` for `www` pointing at Vercel. Use the exact
   values Vercel shows, since they can change. Delete any parking-page records
   the registrar added.
3. HTTPS certificates are issued automatically once DNS resolves, usually
   within minutes. `.app` domains are HTTPS-only by design (HSTS preload), and
   `vercel.json` already sends a `Strict-Transport-Security` header.
4. Set `VITE_SITE_URL=https://researchcoach.app` (Production) and redeploy.
   This adds the canonical link, `og:url` and `sitemap.xml`.
5. Optional: redirect the old address. Add `research-coach-three.vercel.app`
   under Domains and set it to redirect to the new domain.
6. Optional: submit `https://researchcoach.app/sitemap.xml` in Google Search
   Console.

There are no OAuth callbacks or third-party allow-lists to update. Sign-in is
built in, and the API is same-origin, so CORS needs no changes.

---

## Everyday maintenance

| Task | How |
|---|---|
| Ship a change | Push a branch and open a PR. CI runs backend tests on SQLite and Postgres, the frontend build, and browser checks. Vercel posts a preview URL. Merge to deploy. |
| Roll back | Vercel → Deployments → pick the last good one → **Promote to Production**. Instant, no rebuild. |
| See errors | Vercel → project → **Logs**. Every request is logged with method, path, status, duration and a request id. Users see "Reference: <id>" on errors, so search the logs for it. |
| Uptime monitoring | Optional. If you add a free monitor (UptimeRobot, Better Stack) on `https://<domain>/api/health`, check **at most once an hour**: every check wakes the database for ~5 minutes, and frequent checks alone can use a large share of Neon's free compute hours. It returns 503 when the database is unreachable or configuration is missing. |
| Check free-tier usage | Vercel → **Usage**; Neon → **Billing → Usage**. Both pause rather than bill when a limit is reached. |
| Back up the database | Neon keeps a 6-hour restore window on Free. For anything longer, run `pg_dump "$NEON_DIRECT_URL" > backup-$(date +%F).sql` on a schedule you trust. |
| Add a column | Add it to the SQLAlchemy model. On the next deploy, the first request adds the column. Renames, type changes and drops are **not** automatic; write those as SQL and run them against a backup first. |

## Running locally

```bash
# backend (SQLite, demo data seeded automatically)
cd backend && python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
uvicorn app.main:app --reload            # http://localhost:8000/docs

# frontend, in a second terminal (proxies /api to :8000, same as production)
cd frontend && npm install && npm run dev  # http://localhost:5173

# tests
cd backend && python -m pytest
DATABASE_URL=postgresql://coach:coach@localhost:5432/research_coach python -m pytest  # against Postgres (docker compose up db)
cd e2e && npm ci && npm run smoke && npm run flows                                   # with both servers running
```
