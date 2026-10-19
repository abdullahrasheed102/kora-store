# Kora Outfitters — Build Plan

## 1. Database schema (Postgres)

| Table | Key columns |
|---|---|
| `users` | id, email (unique, lowercase), password_hash, name, role (`customer` / `admin`), created_at |
| `addresses` | id, user_id, name, line1, line2, city, state, postal_code, country, is_default |
| `products` | id, slug (unique), name, category, description, fit_notes, material_care, price_cents, is_final_sale, restock_note, image_url, is_active, created_at |
| `product_variants` | id, product_id, sku (unique), size, color, stock, price_cents (nullable override) |
| `orders` | id, order_number (unique, `KO-1001`…), user_id (nullable for guests), email, customer_name, status, status_note, subtotal_cents, shipping_cents, total_cents, shipping_method (`standard` / `express` / `international`), shipping address fields, carrier, tracking_number, estimated_delivery, delivered_at, stripe_session_id, stripe_payment_intent, created_at, updated_at |
| `order_items` | id, order_id, variant_id, product_name, size, color, unit_price_cents, quantity, is_final_sale (snapshotted at purchase) |
| `order_events` | id, order_id, status, note, created_at, created_by (`system` / `admin` / `agent`) |
| `return_requests` | id, order_id, items (JSON: order_item_id + qty), reason, type (`refund` / `exchange`), exchange_details, status (`requested` / `approved` / `label_sent` / `received` / `refunded` / `rejected`), created_by (`customer` / `agent` / `admin`), created_at |
| `support_tickets` | id, order_id (nullable), email, name, subject, summary, priority, status (`open` / `in_progress` / `closed`), source (`agent` / `contact_form`), created_at |
| `policies` | id, key (unique), title, body, updated_at |

Order statuses: `pending_payment`, `processing`, `shipped`, `out_for_delivery`, `delivered`, `delayed`, `partially_shipped`, `cancelled`, `returned`.

## 2. API (all under `/api`)

**Public / customer**
- `GET /products?category=&q=&size=&color=&sort=&page=` · `GET /products/<slug>` · `GET /categories`
- `GET /policies` · `GET /policies/<key>`
- `POST /cart/quote` — body: items (variant_id, qty) + shipping method → returns validated line items, stock warnings, subtotal, shipping, total
- `POST /auth/signup` · `POST /auth/login` · `POST /auth/logout` · `GET /auth/me`
- `GET /account/orders` · `GET /account/orders/<order_number>` · `GET/POST/PUT/DELETE /account/addresses`
- `POST /checkout/session` — creates a `pending_payment` order + Stripe Checkout Session, returns its URL (guests allowed with email)
- `POST /stripe/webhook` — on `checkout.session.completed`: mark `processing`, decrement stock, write event, (later) send confirmation email
- `GET /orders/<order_number>/confirmation?session_id=` — data for the thank-you page
- `POST /orders/track` — body: order_number + email → status, timeline, carrier, tracking, ETA (rate limited; identical "not found" response whether the order number or the email is wrong)
- `POST /returns` — logged-in customer or order_number + email: eligibility check + create request
- `POST /support/contact` — contact form → support ticket

**Admin** (role `admin`)
- Products: list, create, update, deactivate; variants and stock editing
- Orders: list with filters/search, detail, update status (status, carrier, tracking, ETA, note → writes `order_events`)
- Returns: list, approve / reject / mark refunded
- Tickets: list, update status
- `GET /admin/stats` — revenue (7/30 days), orders by status, low-stock variants, open tickets

**Agent** (header `X-Agent-Key`, built in phase 8)
- `POST /agent/orders/lookup` (order_number + email) · `GET /agent/products/search?q=` · `GET /agent/policies`
- `POST /agent/returns/check-eligibility` · `POST /agent/returns` · `POST /agent/tickets` · `POST /agent/orders/<n>/cancel-request`

## 3. Frontend pages (Next.js App Router)
- `/` — hero, featured categories, bestsellers, perks (shipping / returns / 24-7 support)
- `/shop` and `/shop/[category]` — grid with filters (category, size, color, price) and sort; search via `?q=`
- `/products/[slug]` — gallery, size and color pickers with live stock, fit notes, material & care, add to cart, final-sale badge, out-of-stock state with restock note
- Cart drawer + `/cart` — quantities, shipping method, totals from `/cart/quote`
- `/checkout` — email (prefilled when logged in), address, shipping method → redirect to Stripe
- `/order/success` — confirmation with order number
- `/track` — order number + email → status timeline
- `/returns` — start a return (order number + email or from account)
- `/account` — profile, addresses, order history, order detail with timeline and "start a return"
- `/login`, `/signup`
- `/policies/[key]`, `/contact`, `/about`
- `/admin` — dashboard stats; `/admin/products`, `/admin/products/[id]`, `/admin/orders`, `/admin/orders/[number]`, `/admin/returns`, `/admin/tickets` (protected; admin role only)
- Global: header with search and cart count, footer, toasts, loading skeletons, 404 page, SEO metadata and Open Graph images. A small "Demo store by Abdullah Rasheed" banner linking to abdullahrasheed.tech.

## 4. Build phases

Claude builds every phase: frontend, backend and the agent. Abdullah's job is to understand it well enough to explain
it in an interview. Each phase ends with tests passing, a guide in `docs/guide/`, and updates to `docs/ARCHITECTURE.md`,
`docs/INTERVIEW_PREP.md` and `docs/GLOSSARY.md` (see "How we work" in CLAUDE.md).

### How to run each phase
1. **Start a fresh Claude Code session** so the context is clean and focused on one phase.
2. **Run `/output-style explanatory`** so Claude explains its choices while it works.
3. **Enter plan mode** (Shift+Tab) and paste the phase prompt. Read the plan, ask questions, then approve it.
4. **Try it yourself** using the "Try it yourself" steps Claude gives you at the end.
5. **Commit** once the checks pass: `git add -A && git commit -m "Phase N: <topic>"`.
6. **Read the guide** for the phase in `docs/guide/`.
7. **Get quizzed**: ask Claude to quiz you on the phase using `docs/INTERVIEW_PREP.md`.

### Phase 0 — Repo setup
> Read CLAUDE.md and docs/PLAN.md. Set up `backend/`: the app factory, config from environment variables, blueprints, `/api/health` (with a database check), requirements, `.env.example`, docker-compose Postgres and pytest. Set up `frontend/`: Next.js App Router + TypeScript + Tailwind with the design tokens and fonts, the `/api` rewrite to `BACKEND_URL`, the typed API client in `lib/api.ts`, and a placeholder home page that shows `/api/health`.

✅ Done when: both apps run locally, `pytest` passes, and `npm run lint && npm run build` pass.

**Concepts:** app factory, blueprints, config and environment variables, virtual environments, Docker Compose, the `/api` proxy and why it exists, health checks.

### Phase 1 — Database, models and seed
> Build the SQLAlchemy 2.x models for the schema in docs/PLAN.md section 1, the first Alembic migration, and the `flask seed --reset` command that loads `backend/seed/`. Write model tests first.

✅ Done when: the seed loads 20 products, 217 variants, 12 orders and 5 policies.

**Concepts:** relational design, primary and foreign keys, constraints, indexes, ORM vs raw SQL, migrations, money as integer cents (not floats), relative seed dates.

### Phase 2 — Catalog API + storefront
> Build the product, category and policy endpoints with filters, search, sort and pagination, plus tests. Then build the storefront against them: home, shop with filters, category pages, product detail with variant selection and live stock, policies pages, header, footer and 404. Premium look, fully responsive.

✅ Done when: the shop pages show seeded products with working filters, and tests cover each endpoint.

**Concepts:** REST design, query parameters, pagination, N+1 queries, input validation, server vs client components, SEO metadata.

### Phase 3 — Cart and accounts
> Build `/cart/quote` (server-side pricing, shipping rules, stock checks) and the auth routes (signup, login, logout, me) with httpOnly cookie JWTs, CSRF protection and login rate limiting. Then build the cart context, cart drawer, cart page, login, signup and account pages (profile, addresses, order history).

✅ Done when: a user can sign up, log in, build a cart with correct server-calculated totals, and log out.

**Concepts:** never trusting the client, password hashing, JWT vs server sessions, cookies (httpOnly, Secure, SameSite), CSRF, rate limiting, React context.

### Phase 4 — Stripe checkout
> Build the checkout session endpoint and the Stripe webhook handler (signature verification, idempotency, stock decrement in a transaction with row locks), with tests that mock Stripe. Then build the checkout and order success pages.

✅ Done when: card `4242 4242 4242 4242` creates a KO order and stock goes down.

**Concepts:** hosted checkout, webhooks, signature verification, idempotency, database transactions, row locks, race conditions.

### Phase 5 — Order tracking and returns
> Build order tracking (rate limited, no information leaks) and the return eligibility rules from the policy, with one test per rule. Then build the `/track` page with a status timeline, the `/returns` page, and "start a return" from the account.

✅ Done when: KO-1005 is eligible, KO-1007 is refused (over 30 days), and the socks in KO-1011 are refused (final sale).

**Concepts:** business rules as code, test-driven development, user enumeration and how to avoid it, audit timelines (`order_events`).

### Phase 6 — Admin dashboard
> Build role-based access control and the admin endpoints (product and stock management, order status updates that write events, returns, tickets, stats queries). Then build the full admin UI: dashboard with stats, products, orders, returns and tickets.

✅ Done when: an admin can update an order's status (and it appears in the tracking timeline), and a customer gets 403 on every admin route.

**Concepts:** authentication vs authorization, role-based access control, aggregate SQL queries, audit trails.

### Phase 7 — Deploy
> Deploy Flask to Render with Neon Postgres (gunicorn, migrations on deploy, environment variables, health checks, logs, the production Stripe webhook) and the frontend to Vercel with `BACKEND_URL` and production settings. Explain each step as we do it.

✅ Done when: the live site works end to end with a test payment.

**Concepts:** WSGI servers, production config, secrets management, connection pooling, cold starts, debugging from logs.

### Phase 8 — AI support agent (the main event)
This is the part interviewers will ask about most, so it gets the most detailed guide. Planned in detail once the store is live:
1. The `/api/agent/*` endpoints with API-key auth.
2. A LangGraph supervisor with Order, Product and Returns agents, using Groq for routing and Gemini for the specialists.
3. Tools that call the backend, guardrails (verify the order email before sharing data, escalate risky cases), and conversation memory.
4. Evals: 30+ test conversations with expected outcomes, run in CI, plus tracing.
5. A chat widget on the store, then WhatsApp.

✅ Done when: the chat widget answers order, product and return questions using real data, and the eval suite passes in CI.

**Concepts (the guide covers each in depth):**
- **Agents vs chatbots** — a chatbot only replies; an agent decides which actions to take and calls tools.
- **Tool calling** — how the model asks for a function call, how we run it and return the result.
- **The supervisor pattern** — one router agent hands each request to a specialist agent.
- **State and memory** — what the graph state holds, and short-term vs long-term conversation memory.
- **Prompt design** — system prompts, tool descriptions, few-shot examples, structured output.
- **Guardrails** — identity checks before sharing order data, refusing off-topic requests, escalating to a human.
- **Evals** — test conversations with expected outcomes, how to measure success, running them in CI.
- **Cost and latency** — why a small fast model (Groq) routes and a stronger model (Gemini) answers; token budgets.
- **Why LangGraph** — compared with a plain loop, LangChain agents, and other agent frameworks.

## 5. Environment variables
- Agent (phase 8): `GROQ_API_KEY`, `GEMINI_API_KEY`, `AGENT_API_KEY`, `BACKEND_URL`
- Backend: `DATABASE_URL`, `SECRET_KEY`, `JWT_SECRET_KEY`, `FRONTEND_URL`, `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET`, `ADMIN_EMAIL`, `ADMIN_PASSWORD`, `AGENT_API_KEY`
- Frontend: `BACKEND_URL`, `NEXT_PUBLIC_SITE_URL`

## 6. Hosting notes
- **Render free web services sleep when idle**, so the first request after a quiet period is slow. Before you send a demo link to a prospect, open the site once to wake it, or use a free uptime pinger.
- **Neon**: use the pooled connection string, with `sslmode=require`.
- **Stripe**: test mode only. Add the production webhook endpoint `https://<render-app>/api/stripe/webhook` in the Stripe dashboard.

## 7. Nice-to-have later
Discount codes, order confirmation emails (Resend), product reviews, wishlist, image uploads (Cloudinary), analytics.
