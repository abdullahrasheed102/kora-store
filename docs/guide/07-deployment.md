# Phase 7 — Deployment

The step-by-step runbook is [DEPLOY.md](../../DEPLOY.md). This guide explains **why** it's set up the way it is.

## What we built

**Hosting as code**
- `render.yaml`: a Render **Blueprint**, the API's hosting setup written as a file: runtime, region, build and
  start commands, health check and environment variables. Secrets are marked `sync: false` (typed into Render once,
  never in git) or `generateValue: true` (Render makes a random one).
- `backend/start.sh`: runs `flask db upgrade`, then `flask images sync`, then starts gunicorn. Runs on every deploy
  and every time the free instance wakes up.
- `backend/gunicorn.conf.py`: the production web server: one worker, four threads, a 30-second timeout, logs to
  stdout with the `X-Forwarded-For` chain.
- `frontend/vercel.json`: framework and region (`iad1`, next to Render's Virginia and Neon's US East).
- `.github/workflows/expire-unpaid.yml`: an hourly GitHub Actions job that cancels never-paid orders, because
  Render's free plan has no cron jobs.

**Production settings** (`backend/app/config.py`)
- `ProductionConfig` **refuses to start** with unsafe settings and lists every problem at once: weak or placeholder
  secrets, a non-https `FRONTEND_URL`, a remote database without `sslmode=require`, Stripe without both keys, and
  in-memory rate limits with more than one worker.
- `engine_options()`: the connection pool settings for Neon: pre-ping, recycle after 5 minutes, a 10s connect timeout,
  and no prepared statements on the pooled (PgBouncer) endpoint.

**Security headers**
- API (`backend/app/__init__.py`): `nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy: no-referrer`,
  `Content-Security-Policy: default-src 'none'`, and HSTS outside development.
- Website (`frontend/next.config.ts`): a Content Security Policy, HSTS, `nosniff`, `X-Frame-Options`,
  `Referrer-Policy`, `Permissions-Policy`, and no `X-Powered-By`.

**Health checks** (`backend/app/api/health.py`)
- `GET /api/health/live`: *liveness*, with no database. Render's health check uses it.
- `GET /api/health`: *readiness*, with a database query. Use it to check the whole system yourself.

**Tests:** 16 new (production safety checks, the pool settings, liveness without a database, security headers).
308 → 324 backend tests. I also rehearsed the deploy on this machine with production settings (see "Try it yourself").

## Key concepts

- **WSGI server.** Flask is a Python function that turns a request into a response. Something must accept network
  connections and call it: that's a WSGI server (WSGI = Web Server Gateway Interface, the standard way Python web
  apps and servers talk). `flask run` is a development server. **Gunicorn** is a production one: it runs workers,
  restarts stuck ones, and shuts down gracefully.
- **Workers and threads.** A *worker* is a separate process with its own memory. A *thread* runs inside a worker and
  shares its memory. Our requests mostly wait for the database, and threads share that waiting well, so we use 1
  worker × 4 threads.
- **Platform as a Service (PaaS).** Render and Vercel run our code from Git and handle servers, HTTPS certificates
  and restarts. We describe *what* to run, not *how* to run a server.
- **Serverless Postgres.** Neon separates storage from compute. The compute (the part that runs queries) **sleeps**
  after 5 minutes without queries and wakes in about a second. That's why the free plan is cheap, and why idle
  connections disappear.
- **Connection pooling.** Opening a Postgres connection is slow (TLS handshake + login). A pool keeps a few open and
  reuses them. We have *two* pools: SQLAlchemy's inside our app, and Neon's **PgBouncer** in front of the database
  (the `-pooler` hostname), which lets many app instances share a few real database connections.
- **TLS / `sslmode=require`.** Encrypts the connection between Render and Neon. Without it, the database password
  and every row would cross the internet in plain text.
- **Cold start.** The delay when something asleep has to start: Render's free instance (about a minute) and Neon's
  compute (about a second).
- **Liveness vs readiness.** *Liveness*: is the process running? (If not, restart it.) *Readiness*: can it do its
  job right now, e.g. reach the database? Mixing them up causes problems, as explained in "What could go wrong".
- **Infrastructure as code.** Hosting settings live in files (`render.yaml`, `vercel.json`, the workflow) that are
  reviewed and versioned like code, instead of only as clicks in a dashboard.
- **Security headers.** Instructions the server sends to the browser: *only use HTTPS* (HSTS), *don't put me in a
  frame* (clickjacking), *only load scripts and images from these places* (CSP).
- **Fail fast.** Check configuration at startup and refuse to run when it's wrong. A crash with a clear message on
  deploy is much better than a site that runs insecurely.

## How it works here

### `render.yaml`: the API's hosting, as code

```yaml
services:
  - type: web
    name: kora-api
    runtime: python
    plan: free
    region: virginia
    rootDir: backend
    buildCommand: pip install -r requirements.txt
    startCommand: ./start.sh
    healthCheckPath: /api/health/live
    envVars:
      - key: SECRET_KEY
        generateValue: true     # Render makes a random 256-bit value
      - key: DATABASE_URL
        sync: false             # asked for once in the dashboard, never in git
      - key: TRUSTED_PROXY_COUNT
        value: "2"
```

- **Build** installs the pinned packages (`requirements.txt`). **Start** runs `start.sh`.
- Render's **pre-deploy command** would be the usual place for migrations, but the free plan doesn't have it. So
  `start.sh` runs them. That's safe because Alembic records which migrations already ran (the `alembic_version`
  table): on a normal start, `flask db upgrade` checks and does nothing.

### `start.sh`

```bash
set -euo pipefail     # stop at the first failing step
flask db upgrade      # new migrations, if any
flask images sync     # product photos from the manifest (idempotent, Phase 2)
exec gunicorn wsgi:app
```

`set -e` means a failed migration stops the start, so the new code never runs against an old schema. `exec`
replaces the shell with gunicorn, so when Render sends the stop signal on a redeploy, gunicorn receives it and
finishes in-flight requests (`graceful_timeout = 20`).

### `gunicorn.conf.py`

```python
bind = f"0.0.0.0:{os.environ.get('PORT', '10000')}"
workers = int(os.environ.get("WEB_CONCURRENCY", "1"))
worker_class = "gthread"
threads = 4
timeout = 30
access_log_format = '%(t)s "%(r)s" %(s)s %(b)sB %(M)sms xff="%({x-forwarded-for}i)s"'
```

Why one worker? Our rate limits (Phase 3) count requests **in memory**. With 3 workers, each would count separately,
so "5 login attempts per minute" would really be 15. One worker keeps one counter. Scaling to more workers means
moving the counters to Redis (`RATELIMIT_STORAGE_URI=redis://…`). `ProductionConfig` refuses `memory://` with
`WEB_CONCURRENCY > 1`, so this can't happen by accident.

### Production safety checks

```python
# backend/app/config.py
class ProductionConfig(BaseConfig):
    def __init__(self) -> None:
        super().__init__()
        problems = production_problems(self)
        if problems:
            raise RuntimeError("Unsafe production settings:\n- " + "\n- ".join(problems))
```

`production_problems()` returns every problem, not just the first, so one failed deploy shows everything to fix:

| Check | Why |
|---|---|
| `SECRET_KEY`, `JWT_SECRET_KEY`, `SANDBOX_WEBHOOK_SECRET`: 32+ characters, not a placeholder | A guessable JWT secret means anyone can forge an admin session |
| `FRONTEND_URL` starts with `https://` | Payment redirects go there |
| A remote `DATABASE_URL` has `sslmode=require` (or `verify-ca` / `verify-full`) | Encrypts the password and data in transit |
| Stripe needs both keys | Without the webhook secret, no payment could ever be confirmed |
| `memory://` rate limits only with one worker | Several workers would multiply every limit |

### Neon connection settings

```python
def engine_options(database_url: str) -> dict[str, Any]:
    connect_args = {"connect_timeout": 10}
    if "-pooler." in host:
        connect_args["prepare_threshold"] = None
    return {"pool_pre_ping": True, "pool_recycle": 300, "pool_size": 5, "max_overflow": 5, "connect_args": connect_args}
```

- **`pool_pre_ping`**: before handing out a pooled connection, SQLAlchemy runs a tiny check. When Neon's compute
  sleeps, it closes our idle connections. Without the ping, the first request afterwards would fail with "server
  closed the connection unexpectedly".
- **`pool_recycle=300`**: replace connections older than 5 minutes (Neon sleeps after 5 idle minutes).
- **`prepare_threshold=None` on the pooler**: PgBouncer in *transaction* mode may send each transaction over a
  different real connection. psycopg normally *prepares* (pre-compiles) queries it sees often, and a prepared
  statement exists on one real connection only, so a later query could hit a connection where it doesn't exist.
  Turning it off costs a little speed and removes that whole class of error. (Recent PgBouncer versions can track
  prepared statements; this setting keeps us safe either way.)
- **Pooled for the app, and also for migrations.** Alembic's DDL runs inside normal transactions, so the pooled
  endpoint works. If a future migration needs session features (e.g. `CREATE INDEX CONCURRENTLY`), run it with
  Neon's *direct* (non-pooler) connection string.

### Two health checks

```python
@bp.get("/health/live")   # Render's health check
def live():
    return {"status": "ok"}

@bp.get("/health")        # for people and monitoring
def health():
    db.session.execute(text("SELECT 1"))
    ...
```

Render calls its health check every few seconds while the instance runs. If that check ran `SELECT 1`, Neon's
compute would **never sleep** while Render is awake, and an uptime pinger keeping Render awake would use up Neon's
free compute hours. The liveness check has no query, so Neon sleeps while nobody is shopping. A broken database still
fails loudly: `start.sh` runs migrations first (the deploy fails if it can't connect), and `/api/health` reports
`503 "database": "unavailable"`.

### Security headers

**API** (`backend/app/__init__.py`): the API only returns JSON, so its policy is the strictest possible:

```python
SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Content-Security-Policy": "default-src 'none'; frame-ancestors 'none'",
}
# plus Strict-Transport-Security when not in development
```

**Website** (`frontend/next.config.ts`):

```ts
const contentSecurityPolicy = [
  "default-src 'self'",
  "script-src 'self' 'unsafe-inline'",
  "style-src 'self' 'unsafe-inline'",
  "img-src 'self' data: blob: https:",
  "font-src 'self'",
  "connect-src 'self'",
  "frame-ancestors 'none'",
  "form-action 'self'",
  "base-uri 'self'",
  "object-src 'none'",
  "upgrade-insecure-requests",
].join("; ");
```

| Header | What it stops |
|---|---|
| `Strict-Transport-Security` | The browser uses HTTPS for two years, even if someone types `http://`. Stops downgrade attacks |
| `Content-Security-Policy` | Scripts, fonts and API calls only from our own origin; nobody can frame the site; no plugins; forms only post to us |
| `X-Frame-Options: DENY` | The same "no framing" rule for older browsers (clickjacking) |
| `X-Content-Type-Options: nosniff` | The browser must not guess a file is a script |
| `Referrer-Policy` | Other sites see only our domain, not full URLs (which could contain an order number) |
| `Permissions-Policy` | No camera, microphone or location, even if a script asks |

The CSP is only sent by production builds, because the dev server needs `eval()` for fast refresh.

**Why `'unsafe-inline'` for scripts?** Next.js puts small inline `<script>` tags in every page to pass data to
React. The strict alternative is a *nonce* (a random value per response, allowed in the CSP). But a nonce has to be
different on every request, which forces every page to be rendered per request. We'd lose the prerendered static
shell from Phase 2. We chose the static shell and keep the rest of the policy strict. It still blocks scripts from
other domains, framing, plugins and `<base>` tricks, and React escapes everything we render.

### Cookies in production

Already set since Phase 3, and now tested under production config:

```python
JWT_COOKIE_SECURE = True     # sent over HTTPS only
JWT_COOKIE_SAMESITE = "Lax"  # not sent on cross-site POSTs
JWT_COOKIE_CSRF_PROTECT = True
```

The browser only ever talks to `kora-outfitters.vercel.app`, and Vercel forwards `/api/*` to Render. So the
cookie is a **first-party** cookie on the Vercel domain. The browser never sees `onrender.com`, which means no CORS
and no third-party cookie problems (many browsers block third-party cookies).

### Finding the real client IP

```text
Browser (203.0.113.7) → Vercel → Render's load balancer → gunicorn
X-Forwarded-For: "203.0.113.7, <Vercel's IP>"
```

Each proxy adds the address it received the request from. `ProxyFix(x_for=2)` takes the **second value from the
right**, the one Vercel saw. We trust only the values our own proxies added: a value further left could be typed by
the client to dodge rate limits. The gunicorn log line prints the full chain (`xff="…"`), and step 5 of DEPLOY.md
checks it on the live site. In the local rehearsal, Next's own server didn't add the header (`xff="-"`). That's why
we check it in production instead of assuming.

### The hourly job

```yaml
on:
  schedule:
    - cron: "17 * * * *"
```

It installs the backend and runs `flask orders expire-unpaid --older-than 60`, the same command we wrote in Phase 4.
It needs only `DATABASE_URL` (a GitHub secret). The app's other required secrets are random throwaway values,
because this command never signs anything. Without the secret, the job skips itself instead of failing every hour.

## Request flow

```mermaid
sequenceDiagram
    autonumber
    participant B as Browser
    participant V as Vercel (Next.js, iad1)
    participant R as Render (gunicorn + Flask, Virginia)
    participant N as Neon (PgBouncer → Postgres)

    Note over R,N: Deploy: start.sh → flask db upgrade → flask images sync → gunicorn
    B->>V: GET https://kora-outfitters.vercel.app/products/linen-button-up-shirt
    V-->>B: static shell (HTML + CSP and HSTS headers), streamed
    V->>R: GET /api/products/linen-button-up-shirt (server component, server to server)
    R->>N: SELECT … (TLS, pooled connection, pre-ping)
    N-->>R: rows
    R-->>V: JSON (+ nosniff, CSP default-src 'none')
    V-->>B: product details streamed into the page
    B->>V: POST /api/auth/login (cookie + X-CSRF-TOKEN)
    V->>R: rewrite → POST /api/auth/login, X-Forwarded-For: client, Vercel
    R->>R: ProxyFix(x_for=2) → real client IP → rate limit
    R-->>V: 200 + Set-Cookie (Secure, HttpOnly, SameSite=Lax)
    V-->>B: same response: the cookie belongs to vercel.app (first-party)
    loop every few seconds
        R->>R: Render health check → GET /api/health/live (no database)
    end
```

## Design decisions and alternatives

| Decision | Alternatives | Why we chose this |
|---|---|---|
| Render + Vercel + Neon, all free | One VPS (DigitalOcean, Hetzner); Fly.io; Railway; AWS | $0, no servers to patch, deploy on `git push`. A VPS teaches more Linux, but every security update is then our job |
| Migrations in `start.sh` | Render pre-deploy command (paid); in the build step; by hand | The free plan has no pre-deploy step. The build step may run while the old version still serves traffic. By hand gets forgotten. Alembic makes repeated runs safe |
| 1 worker × 4 threads | Several workers; async workers (gevent) | Fits 512 MB; correct in-memory rate limits; our code is ordinary blocking code (SQLAlchemy, Stripe SDK) that threads handle well |
| Rate limits in memory | Render Key Value (Redis) | One process means one counter. The counters reset when the free instance restarts, which is acceptable for a demo. Redis is a one-variable change when we need it |
| Neon **pooled** endpoint | Direct connection | Survives many connections (e.g. several app instances plus the GitHub job). The direct connection is kept for special migrations |
| Liveness check without the database | One `/api/health` for everything | Lets Neon sleep (free compute hours); a database blip doesn't make Render restart a healthy process |
| Seed from the laptop | Render Shell (paid); a seed in `start.sh` | One-time job; `start.sh` must never seed (it would run on every start) |
| GitHub Actions for the hourly job | Render Cron Job (paid); cron-job.org calling a secret HTTP endpoint | Free, reuses the existing CLI command, and adds no new public endpoint. The cost: the database URL is also stored as a GitHub secret |
| CSP with `'unsafe-inline'` scripts | Nonce-based CSP | A nonce forces every page to render per request and loses the static shell. We keep everything else strict |
| Region: US East everywhere | Frankfurt (closer to Pakistan) | Each page render makes several API calls, so Vercel ↔ Render ↔ Neon must be close together. US East is closest to most recruiters. Moving all three to Frankfurt is equally valid |
| Sandbox payments by default | Stripe test mode | Stripe doesn't accept accounts from Pakistan. The sandbox uses the same signed-webhook path, so the live demo shows the real flow |

## What could go wrong

- **The free Render instance is asleep.** The first visitor waits about a minute, and pages can time out. Open the
  site before a demo, or use the keep-awake ping (DEPLOY.md step 8).
- **`BACKEND_URL` set after the first Vercel build.** The rewrite is baked in at build time, so `/api` keeps pointing
  at the old value until you redeploy.
- **Wrong `TRUSTED_PROXY_COUNT`.**
  - Too low: the rate limiter trusts a value the client can fake, so an attacker can set their own IP.
  - Too high: ProxyFix finds too few entries and keeps Render's load balancer IP, so **every visitor shares one rate
    limit**, and one person's failed logins can lock everyone out.
  
  Check the `xff=` log field (DEPLOY.md step 5).
- **A health check that queries the database** would keep Neon awake 24/7 and use up the free compute. It could also
  make Render restart a healthy process during a short database hiccup.
- **`flask seed --reset` against production** deletes every order and account. `start.sh` never seeds, and plain
  `flask seed` refuses a database that has data.
- **A migration that fails halfway on startup.** `set -e` stops gunicorn from starting, so the old version keeps
  serving and the deploy shows as failed. Postgres runs our DDL inside a transaction, so a failed migration rolls
  back cleanly.
- **Secrets in git.** `.env` files are git-ignored, and Render secrets are `sync: false` or generated. DEPLOY.md
  step 1 checks before the first push. If a secret ever leaks, rotate it: Neon → reset password; Render →
  regenerate.
- **Rate limits reset on restart**, because they're in memory. Acceptable for a demo, not for a real shop: use Redis
  there.
- **Neon's free limits.** Storage is tiny for us. Compute hours are what to watch: Neon → Usage.

## Try it yourself

1. **Rehearse production locally** (what I ran before writing DEPLOY.md):
   ```bash
   cd backend && source .venv/bin/activate
   docker compose exec db psql -U kora -c "CREATE DATABASE kora_rehearsal"
   APP_ENV=production PORT=5001 DATABASE_URL=postgresql://kora:kora@localhost:5432/kora_rehearsal \
     SECRET_KEY=$(openssl rand -hex 32) JWT_SECRET_KEY=$(openssl rand -hex 32) \
     SANDBOX_WEBHOOK_SECRET=$(openssl rand -hex 32) FRONTEND_URL=https://localhost:3001 ./start.sh
   ```
   In another terminal: `curl -sI localhost:5001/api/health/live` and look at the headers. Stop it with Ctrl+C and
   drop the database: `docker compose exec db psql -U kora -c "DROP DATABASE kora_rehearsal"`.
2. **See fail-fast:** run the same command with `FRONTEND_URL=http://localhost:3001` and `SECRET_KEY=short`. It
   refuses to start and lists both problems.
3. **See the CSP:** `cd frontend && npm run build && npx next start -p 3001`, then
   `curl -sI localhost:3001 | grep -i content-security`.
4. **After deploying:** `curl -sI https://kora-outfitters.vercel.app/` and `curl https://kora-api.onrender.com/api/health`.
   Open the Render **Logs** tab while you click around the live site.

## Explain it in 60 seconds

> "The store runs on three managed services, all on free plans. Next.js is on Vercel, Flask is on Render behind
> gunicorn, and Postgres is on Neon, all in US East so the server-to-server calls are short. The browser only talks
> to Vercel, which forwards `/api` to Render, so the session cookie is first-party and there's no CORS. Hosting is
> code: a `render.yaml` Blueprint, a start script that runs Alembic migrations and an idempotent image sync before
> gunicorn, and a GitHub Actions job for the hourly clean-up, because the free plan has no cron. The production
> config fails fast: it refuses to start with weak secrets, a non-https frontend URL, or a database URL without TLS.
> For Neon I use the pooled endpoint with pre-ping and no prepared statements, because PgBouncer in transaction
> mode can't keep them. Render's health check is a liveness check that doesn't touch the database, so Neon's
> compute can sleep. Both apps send security headers: a strict CSP on the API and a practical one on the site, plus
> HSTS. I rehearsed the whole deploy locally with production settings, including a sandbox payment, before going
> live."
