# Deploying Kora Outfitters

The step-by-step runbook. For **why** each piece is set up this way, read
[docs/guide/07-deployment.md](docs/guide/07-deployment.md).

```mermaid
flowchart LR
    B[Browser] -->|https| V["Vercel<br/>Next.js frontend<br/>kora-outfitters.vercel.app"]
    V -->|"/api/* rewrite<br/>+ server components"| R["Render<br/>Flask + gunicorn<br/>kora-api.onrender.com"]
    R -->|"TLS, pooled"| N[("Neon<br/>Postgres")]
    S[Stripe, optional] -->|signed webhook| R
    G[GitHub Actions<br/>hourly] -->|flask orders expire-unpaid| N
```

Everything below fits the **free plans**. Total cost: $0.

| What | Where | Name we use |
|---|---|---|
| Code | GitHub | `kora-store` |
| Database | Neon, AWS US East (N. Virginia) | project `kora` |
| API | Render, Virginia | `kora-api` → `https://kora-api.onrender.com` |
| Website | Vercel, `iad1` (Washington, D.C.) | `kora-outfitters` → `https://kora-outfitters.vercel.app` |

If a name is taken, you'll get a slightly different URL. Write down the real URLs and use them wherever
this file says `kora-api.onrender.com` or `kora-outfitters.vercel.app`.

---

## Step 1: Push the code to GitHub

Render and Vercel deploy straight from a GitHub repository, and redeploy on every push to `main`.

1. Check that no secret file is tracked. Both commands must print nothing:
   ```bash
   cd ~/Documents/kora-store
   git ls-files | grep -E '(^|/)\.env(\.local)?$'
   git status --short --ignored | grep -E 'image-originals|\.env$' | grep -v '^!!'
   ```
2. Commit everything (see the commit commands in the chat, or `git add -A && git commit`).
3. Create an **empty** repository on GitHub: github.com → **New repository** → name `kora-store` → Public
   (it's a portfolio) → **don't** add a README, .gitignore or license → **Create repository**.
4. Connect and push:
   ```bash
   git remote add origin git@github.com:<your-username>/kora-store.git   # or the https:// URL GitHub shows
   git push -u origin main
   ```

✅ Done when: the repository page on GitHub shows `backend/`, `frontend/`, `render.yaml` and `DEPLOY.md`.

---

## Step 2: Create the database on Neon

1. Go to **neon.tech** → **Sign up** → continue with GitHub.
2. **Create project**: name `kora`, Postgres version **17** (same as local), region **AWS US East 1 (N. Virginia)**.
3. On the project dashboard, click **Connect**. Turn **Connection pooling ON**. Copy the connection string.
   It looks like:
   ```text
   postgresql://neondb_owner:•••@ep-xxxx-xxxx-pooler.us-east-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require
   ```
   The host must contain `-pooler`, and it must end with `sslmode=require`. Keep it secret: it contains the
   password.
4. Create the tables and the demo data **from your laptop** (Render's free plan has no shell):
   ```bash
   cd ~/Documents/kora-store/backend && source .venv/bin/activate
   read -rs NEON_URL          # paste the connection string, press Enter (it isn't shown or saved in history)
   export NEON_URL
   DATABASE_URL="$NEON_URL" flask db upgrade
   read -rs ADMIN_PASSWORD    # choose a NEW admin password (12+ characters), press Enter
   DATABASE_URL="$NEON_URL" ADMIN_EMAIL="admin@kora.test" ADMIN_PASSWORD="$ADMIN_PASSWORD" flask seed
   DATABASE_URL="$NEON_URL" flask images check | head -3
   ```
   - `flask seed` without `--reset` refuses to run on a database that already has data. **Never run
     `flask seed --reset` against Neon** once real orders exist.
   - Use a different admin email if you like. This is the login for `/admin` on the live site.

✅ Done when: `flask seed` prints "Seeded 20 products…" and "Synced product images: 65 added", and `images check`
shows no missing photos.

---

## Step 3: Deploy the API on Render

1. Go to **render.com** → **Get Started** → sign up with GitHub. Allow access to the `kora-store` repository.
2. **New** → **Blueprint** → choose `kora-store`. Render finds `render.yaml` and shows one service, `kora-api`.
3. Fill in the values Render asks for (the `sync: false` ones):
   | Key | Value |
   |---|---|
   | `DATABASE_URL` | the Neon **pooled** connection string from step 2 |
   | `FRONTEND_URL` | `https://kora-outfitters.vercel.app` (the Vercel URL you'll create in step 4, no trailing `/`) |
   | `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET` | leave empty (we use the sandbox) |
4. **Apply**. Open the service → **Logs** and watch. You should see, in order:
   - `pip install …` (the build)
   - `INFO [alembic.runtime.migration] …` (migrations: nothing to do, step 2 already ran them)
   - `Policies: 0 added, 0 updated, 5 unchanged.` (only changes when a policy's `version` goes up)
   - `Synced product images: 0 added, 0 updated, 65 unchanged, 0 removed.`
   - `Listening at: http://0.0.0.0:10000` and then **"Your service is live"**.
5. Test it:
   ```bash
   curl https://kora-api.onrender.com/api/health          # {"database":"ok","status":"ok"}
   curl -sI https://kora-api.onrender.com/api/health/live | grep -iE 'strict-transport|x-frame|content-security'
   ```

If it fails, the log says why. "Unsafe production settings" lists exactly which variable is wrong (see
Troubleshooting below).

✅ Done when: `/api/health` returns `"database":"ok"`.

---

## Step 4: Deploy the website on Vercel

1. Go to **vercel.com** → **Sign up** → continue with GitHub (Hobby plan).
2. **Add New…** → **Project** → import `kora-store`.
3. Configure:
   - **Project name:** `kora-outfitters`
   - **Root Directory:** click **Edit** → choose `frontend`. Framework preset: **Next.js** (detected).
   - **Environment Variables:**
     | Key | Value |
     |---|---|
     | `BACKEND_URL` | `https://kora-api.onrender.com` (no trailing `/`) |
     | `NEXT_PUBLIC_SITE_URL` | `https://kora-outfitters.vercel.app` |
     | `NEXT_PUBLIC_ASSISTANT_ENABLED` | `false` |
4. **Deploy**. The build takes 1–2 minutes.
5. If Vercel gave a **different** URL than the `FRONTEND_URL` you entered on Render, fix Render: service →
   **Environment** → edit `FRONTEND_URL` → **Save, rebuild, and deploy**.

`BACKEND_URL` is read **at build time** (for the `/api` rewrite). If you change it later, redeploy on Vercel:
Deployments → ⋯ → **Redeploy**.

✅ Done when: `https://kora-outfitters.vercel.app` shows the homepage with photos and products.

---

## Step 5: Check the live site end to end

1. **Shop and pay:** add something to the bag → Checkout → fill in a US address → **Pay** → on the sandbox page
   click **Use · Succeeds** → enter a name → Pay. You land on the success page with an order number (`KO-10xx`).
2. **Track it:** `/track` with that order number and the email you used.
3. **Admin:** `/login` with the admin email and password from step 2 → you land on `/admin` → the order is there.
4. **Security headers:**
   ```bash
   curl -sI https://kora-outfitters.vercel.app/ | grep -iE 'content-security|x-frame|strict-transport|referrer'
   ```
5. **The real client IP** (needed for fair rate limits). Find your IP with `curl -s https://ifconfig.me`. Then try a
   wrong password once on `/login`, and in Render → **Logs** find the `POST /api/auth/login` line. Its `xff="…"`
   shows the X-Forwarded-For chain:
   - `xff="<your IP>, <another IP>"` → 2 entries → `TRUSTED_PROXY_COUNT=2` is right (the default in `render.yaml`).
   - `xff="<your IP>"` → 1 entry → set `TRUSTED_PROXY_COUNT=1` in Render → Environment.

   If the count is too high, every visitor shares one rate-limit bucket. If it's too low, an attacker can fake their
   IP. The guide explains both.

✅ Done when: a sandbox payment creates an order you can track and see in the admin.

---

## Step 6 (optional): Stripe test mode

Stripe doesn't accept accounts from Pakistan, which is why the store ships with the **sandbox** provider. Only do
this step if you have a Stripe account in a supported country. Never use live keys: the app refuses to start with
`sk_live_…`.

1. Stripe Dashboard → make sure **Test mode** is on → **Developers → API keys** → copy the **Secret key**
   (`sk_test_…`).
2. **Developers → Webhooks → Add endpoint**:
   - URL: `https://kora-api.onrender.com/api/stripe/webhook`. That's Render directly, not Vercel: the webhook comes
     from Stripe's servers, not a browser.
   - Events: `checkout.session.completed`, `checkout.session.async_payment_succeeded`,
     `checkout.session.expired`, `checkout.session.async_payment_failed`.
   - Copy the **Signing secret** (`whsec_…`).
3. Render → `kora-api` → **Environment**: `PAYMENT_PROVIDER=stripe`, `STRIPE_SECRET_KEY=sk_test_…`,
   `STRIPE_WEBHOOK_SECRET=whsec_…` → Save and deploy.
4. Pay with card `4242 4242 4242 4242`, any future date, any CVC. In Stripe → Webhooks → your endpoint, the
   event shows **200**.

To switch back: set `PAYMENT_PROVIDER=sandbox`.

---

## Step 7: Turn on the hourly clean-up job

`.github/workflows/expire-unpaid.yml` cancels orders that were never paid. It skips itself until it has a database.

1. GitHub → repository → **Settings → Secrets and variables → Actions → New repository secret**:
   name `DATABASE_URL`, value: the same Neon pooled connection string.
2. **Actions** tab → **Expire unpaid orders** → **Run workflow**. The log ends with `Expired 0 unpaid order(s).`

---

## Step 8 (optional): Keep the API awake

Render's free web service **sleeps after 15 minutes** without traffic. The next visitor then waits about a minute
while it starts. Before sending the link to someone, open the site once. Or:

- **cron-job.org** (free) → new cron job → URL `https://kora-api.onrender.com/api/health/live` → every 10 minutes.
- Use `/api/health/live`, **not** `/api/health`. The live check doesn't touch the database, so Neon can still sleep
  and you stay inside Neon's free compute hours.
- One always-on free service uses about 744 of Render's 750 free hours a month, so don't keep a second free service
  awake as well.

---

## Updating the live site

| Change | What to do |
|---|---|
| Code | `git push`. Vercel and Render both redeploy `main` automatically |
| Database schema | Add the migration and push. `start.sh` runs `flask db upgrade` on Render's next start |
| Product photos | `cd frontend && npm run images`, commit the `.webp` files **and** `backend/seed/image-manifest.json`, push. `start.sh` runs `flask images sync` |
| Policy text | Edit it in Admin → Policies (live at once), **or** change `backend/seed/policies.json` and raise that policy's `version`, then push. `start.sh` runs `flask policies sync`, which only applies higher versions |
| A Render environment variable | Render → Environment → Save, rebuild, and deploy |
| `BACKEND_URL` / `NEXT_PUBLIC_*` on Vercel | Change it, then **Redeploy** (they're baked in at build time) |

## Troubleshooting

| Symptom | Likely cause and fix |
|---|---|
| Render log: `Unsafe production settings: - FRONTEND_URL must be an https:// URL` | Set `FRONTEND_URL` to the `https://…vercel.app` URL |
| `… DATABASE_URL must end with ?sslmode=require` | Copy the string from Neon's **Connect** dialog again; keep the `?sslmode=require…` part |
| `Missing required environment variable: DATABASE_URL` | You skipped it in the Blueprint form: Render → Environment → add it |
| `/api/health` → `"database":"unavailable"` | Wrong password or host in `DATABASE_URL`, or the Neon project is suspended. The full error is in the Render logs |
| Website shows "Something went wrong" on every page | `BACKEND_URL` on Vercel is wrong or Render is asleep/failing. Open `https://kora-api.onrender.com/api/health` |
| Pages time out right after a quiet period | Render was asleep (about a minute to wake). Reload, or set up step 8 |
| Payment succeeds but you return to `http://localhost:3000` | `FRONTEND_URL` on Render still points at localhost |
| Paying on a Vercel *preview* URL returns you to the production site | Expected: the API sends shoppers back to `FRONTEND_URL`. Test payments on the production URL |
| `relation "…" does not exist` | Migrations didn't run: check the start of the Render log, or run step 2's `flask db upgrade` again |
| Product photos missing | `image-manifest.json` or the `.webp` files weren't committed. Commit both and push |
