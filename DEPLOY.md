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
    R -->|"HTTPS API"| E["Resend<br/>email"]
    G2[GitHub Actions<br/>every 5 min] -->|"POST /api/email/outbox/process"| R
```

Everything below fits the **free plans**. Total cost: $0.

| What | Where | Name we use |
|---|---|---|
| Code | GitHub | `kora-store` |
| Database | Neon, AWS US East (N. Virginia) | project `kora` |
| API | Render, Virginia | `kora-api` → `https://kora-api.onrender.com` |
| Website | Vercel, `iad1` (Washington, D.C.) | `kora-outfitters` → `https://kora-outfitters.vercel.app` |
| Email | Resend (free: 100 emails a day) | sends from `orders@kora.abdullahrasheed.tech` |

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
- Once step 9's email job runs every 5 minutes, it keeps the API awake too, so you don't need a pinger. It still
  lets Neon sleep: the endpoint only queries the database when an email might be waiting.

---

## Step 9: Email with Resend (phase 8A)

The store emails customers when an order is placed, shipped, delivered, cancelled or refunded, and emails **you**
when a support ticket is created. Read [docs/guide/08a-email-notifications.md](docs/guide/08a-email-notifications.md)
for how it works. Do the steps **in this order**: the API refuses to start with `EMAIL_PROVIDER=resend` until the
Resend key, the From address and your own address are set.

### 9.1 Resend account and API key

1. Sign up at [resend.com](https://resend.com) with your own email.
2. **API Keys → Create API key**. Name `kora-api`, permission **Sending access**, domain: all (or your domain once
   it exists). Copy the key (`re_…`). Resend shows it only once.

### 9.2 Verify the sending domain (SPF and DKIM)

Mail servers only trust email from a domain that proves the sender is allowed to use it. We send from a
**subdomain**, `kora.abdullahrasheed.tech`, so the store's email can never hurt the reputation of your main address.

1. Resend → **Domains → Add domain** → `kora.abdullahrasheed.tech`, region **North Virginia (us-east-1)**
   (next to Render and Neon).
2. Resend shows 3 or 4 DNS records. The domain was bought at **get.tech**, and its DNS is hosted there too
   (nameservers `tech-domains.*.orderbox-dns.com`; check with `dig NS abdullahrasheed.tech +short`). So add them in
   get.tech's control panel → your domain → **Manage DNS**: the same screen where the `kora` CNAME for Vercel lives.
   It has a separate tab per record type (TXT, MX, …):

   | Type | Name (host) | Value | What it is |
   |---|---|---|---|
   | TXT | `resend._domainkey.kora` | `p=MIGfMA0…` (long) | **DKIM**: the public key that checks our emails' signatures |
   | MX | `send.kora` | `feedback-smtp.us-east-1.amazonses.com`, priority 10 | Where bounce reports go |
   | TXT | `send.kora` | `v=spf1 include:amazonses.com ~all` | **SPF**: which servers may send for this domain |
   | TXT | `_dmarc.kora` | `v=DMARC1; p=none;` | **DMARC** (recommended): what to do with mail that fails the checks |

   The website already uses `kora` itself (a CNAME to Vercel). These records sit on *different* names
   (`send.kora`, `resend._domainkey.kora`, `_dmarc.kora`), so they don't clash with it.

   Copy the values from **your** Resend page, not from this table. Most DNS panels add the main domain for you,
   so the host is `resend._domainkey.kora`, not the full `resend._domainkey.kora.abdullahrasheed.tech`. If your
   panel shows the full name after saving, that's right. If it shows the domain twice, remove the extra part.
3. Check the records are public before asking Resend (each command should print the value you entered):
   ```bash
   dig TXT resend._domainkey.kora.abdullahrasheed.tech +short
   dig TXT send.kora.abdullahrasheed.tech +short
   dig MX  send.kora.abdullahrasheed.tech +short
   dig TXT _dmarc.kora.abdullahrasheed.tech +short
   ```
   If one still prints nothing after about 30 minutes, look at its host field in the panel. If it reads
   `send.kora.abdullahrasheed.tech` and the panel *also* adds the domain, the real name became
   `send.kora.abdullahrasheed.tech.abdullahrasheed.tech`. Change the host to the short form, `send.kora`.
4. Click **Verify DNS records**. It usually takes a few minutes (sometimes up to an hour). Wait until the domain
   shows **Verified**.

Until the domain is verified, Resend only delivers to **your own Resend account address**. That's enough for the
first test, with `EMAIL_FROM=Kora Outfitters <onboarding@resend.dev>`.

### 9.3 Add the variables on Render (before you push the code)

Render → `kora-api` → **Environment** → **Add environment variable** for each row, then **Save, rebuild, and deploy**:

| Key | Value |
|---|---|
| `EMAIL_PROVIDER` | `resend` |
| `RESEND_API_KEY` | the `re_…` key from 9.1 |
| `EMAIL_FROM` | `Kora Outfitters <orders@kora.abdullahrasheed.tech>` |
| `ADMIN_NOTIFY_EMAIL` | your own inbox (ticket alerts, and the Reply-To on customer emails) |
| `OUTBOX_CRON_SECRET` | run `python3 -c "import secrets; print(secrets.token_hex(32))"` and paste the result |
| `EMAIL_DAILY_CAP` | `80` |
| `EMAIL_RECIPIENT_DAILY_CAP` | `10` |
| `EMAIL_GUEST_ORDER_DAILY_CAP` | `2` |
| `TURNSTILE_SECRET_KEY` | the **secret** key from step 10 (do step 10 first) |

Why before pushing: the Blueprint (`render.yaml`) sets `EMAIL_PROVIDER=resend` on the next deploy. If the key isn't
there yet, the new version refuses to start (Render keeps the old one running, so the site stays up, but the deploy
fails). Then push the code. Its first start runs the new migration (`email_outbox`, `verified_emails`).

### 9.4 Turn on the 5-minute retry job

`.github/workflows/email-outbox.yml` retries emails that couldn't be sent at once. It skips itself until it has
two secrets. GitHub → repository → **Settings → Secrets and variables → Actions → New repository secret**:

- `BACKEND_URL` = `https://kora-api.onrender.com` (your Render URL, no trailing slash)
- `OUTBOX_CRON_SECRET` = the same value you set on Render in 9.3

Then **Actions** → **Email outbox** → **Run workflow**. The log ends with JSON like
`{"skipped": false, "sent": 0, …}` (the first run after a restart checks the database) or `{"skipped": true}`.

### 9.5 Check it works

1. Sign up on the live site with **your real email**. You land on "Check your email", and a "Confirm your email"
   message arrives within a minute. Click it → **Confirm my email** → your account page says "Email confirmed".
2. Place a cash-on-delivery order while logged in. The order confirmation arrives within a minute.
3. Log out and place a guest order (the Turnstile box appears) with a second address of yours. Its confirmation
   arrives directly.
4. Send the contact form. The ticket alert arrives at `ADMIN_NOTIFY_EMAIL`.
5. Resend → **Emails** shows each one as **Delivered**.

---

## Step 10: Cloudflare Turnstile (the bot check on guest checkout)

Guests get order emails without confirming their address, so bots must not be able to place guest orders.
Turnstile is Cloudflare's free CAPTCHA alternative. **You don't need to move your domain or DNS to Cloudflare**:
you only need a free Cloudflare account. The **site key** is public (it's in the page). The **secret key** goes only
on Render. The API refuses to start in production without the secret.

### 10.1 Create the widget

1. Go to https://dash.cloudflare.com and sign up (free) or log in.
2. In the left menu, open **Turnstile** (Cloudflare moves menus now and then: if you don't see it, use the search
   box at the top and type "Turnstile").
3. **Add widget**:
   - **Widget name:** `Kora checkout`
   - **Hostnames:** `kora.abdullahrasheed.tech`. Add your `….vercel.app` address too if you ever test there.
     The widget only works on these hostnames. Locally we use test keys, so `localhost` isn't needed.
   - **Widget mode:** **Managed** (recommended: invisible for most visitors, a checkbox only when unsure)
   - Pre-clearance: **No**
4. **Create**. Cloudflare shows two values:
   - **Site Key** (starts with `0x4…`): public, goes to **Vercel**
   - **Secret Key**: private, goes to **Render**. Treat it like a password.

### 10.2 Add the keys

1. **Render** → `kora-api` → **Environment** → add `TURNSTILE_SECRET_KEY` = the **Secret Key** → Save.
   (Also in the step 9.3 table.)
2. **Vercel** → `kora-outfitters` → **Settings → Environment Variables** → add `TURNSTILE_SITE_KEY` = the
   **Site Key**, for **Production** (and Preview if you use it) → Save. The checkout page reads it on the server, so
   it has no `NEXT_PUBLIC_` prefix. It takes effect on the next deploy, which the push will trigger.

### 10.3 Check it works (after the push)

- Log out → add something to the bag → `/checkout`. A small Turnstile box appears above the Pay button, and the button
  stays disabled until it shows a tick.
- Logged in, there is no box.
- Turnstile dashboard → your widget: the analytics show the solves within a few minutes.


---

## Updating the live site

| Change | What to do |
|---|---|
| Code | `git push`. Vercel and Render both redeploy `main` automatically |
| Database schema | Add the migration and push. `start.sh` runs `flask db upgrade` on Render's next start |
| Product photos | `cd frontend && npm run images`, commit the `.webp` files **and** `backend/seed/image-manifest.json`, push. `start.sh` runs `flask images sync` |
| Policy text | Edit it in Admin → Policies (live at once), **or** change `backend/seed/policies.json` and raise that policy's `version`, then push. `start.sh` runs `flask policies sync`, which only applies higher versions |
| A Render environment variable | Render → Environment → Save, rebuild, and deploy |
| Switch email off quickly | Render → Environment → `EMAIL_PROVIDER=log` → Save. Emails are then only written to the log |
| `BACKEND_URL` / `NEXT_PUBLIC_*` / `TURNSTILE_SITE_KEY` on Vercel | Change it, then **Redeploy** (they're used at build time) |

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
| Render log: `EMAIL_PROVIDER=resend needs RESEND_API_KEY` (or `EMAIL_FROM`, `ADMIN_NOTIFY_EMAIL`) | Add the missing variable (step 9.3) |
| No email arrives | Neon → SQL Editor: `select kind, to_email, status, suppressed_reason, last_error from email_outbox order by id desc limit 10;`. `suppressed` + `unverified`: the address hasn't clicked its confirmation link. `blocked_domain`: an `@example.com` or `.test` address (never emailed). `failed`: read `last_error` |
| `last_error` says `Resend 403 … domain is not verified` | Finish step 9.2, or use `onboarding@resend.dev` as the From address while testing (it only delivers to your own Resend address) |
| Emails land in spam | Check that the DKIM, SPF and DMARC records all show **Verified** in Resend. Brand-new domains have no reputation yet, so the first few emails may go to spam anyway |
| Render log: `TURNSTILE_SECRET_KEY is required` | Do step 10 and add the secret on Render |
| Render log: `TURNSTILE_SECRET_KEY is one of Cloudflare's test keys` | You pasted a `1x0000…` test key: use the widget's real Secret Key |
| Checkout: the Turnstile box shows an error, or "Invalid domain" | The site's hostname isn't in the widget's hostname list (step 10.1), or `TURNSTILE_SITE_KEY` on Vercel is wrong. Fix it and redeploy Vercel |
| Guest checkout says "The security check didn't pass" | The site key (Vercel) and secret key (Render) come from different widgets. Copy both from the same one |
| Guest checkout says "We couldn't run the security check" | Render couldn't reach Cloudflare (guest orders fail closed). Usually brief; check Render logs for `Turnstile siteverify failed` |
| Email outbox workflow fails with `401` | `OUTBOX_CRON_SECRET` differs between GitHub and Render: paste the same value in both |
