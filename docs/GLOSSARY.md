# Glossary

Technical terms used in this project, in alphabetical order. Each entry says what the term means in plain English
and where it appears in Kora Outfitters.

---

**12-factor app** — A well-known list of rules for building web apps that are easy to deploy. One rule: keep
config in environment variables, not in code. *Here:* `backend/app/config.py`.

**401 vs 403** — 401: not authenticated ("log in"). 403: authenticated but not allowed. *Here:* admin routes return
401 without a cookie and 403 for customers.

**415 Unsupported Media Type** — The response when a request body isn't in a format the server accepts. *Here:*
anything that isn't JSON.

**429 Too Many Requests** — The response when a rate limit is hit. Comes with a `Retry-After` header.

**AbortController** — A browser API for cancelling a `fetch` request. *Here:* cancelling an outdated cart quote.

**Abstract base class (ABC)** — A Python class that declares methods without implementing them. Subclasses must
implement every `@abstractmethod`, or they can't be created. *Here:* `PaymentProvider` in
`backend/app/payments/base.py`.

**Adapter pattern** — A class that translates between the interface your code expects and the one another system
offers. *Here:* `StripeProvider` and `SandboxProvider`.

**Aggregate query** — SQL that summarises many rows into a few numbers (`SUM`, `COUNT`, `GROUP BY`). *Here:* the
admin dashboard stats.

**Alembic** — A tool that creates and runs database **migrations** for SQLAlchemy. *Here:* used through
Flask-Migrate from Phase 1.

**Annotated (type hint)** — A Python way to attach extra settings to a type. SQLAlchemy reads it to reuse column
settings. *Here:* `IntPK`, `CreatedAt` in `backend/app/models/types.py`.

**API (Application Programming Interface)** — A set of URLs a program can call to get data or do actions. Our API
returns JSON. *Here:* every Flask route under `/api`.

**App factory (application factory)** — A function that builds and returns the app, instead of creating it at
import time. Makes testing easy. *Here:* `create_app()` in `backend/app/__init__.py`.

**argon2 (argon2id)** — A password hashing algorithm designed to be slow and memory-hungry, so stolen hashes are hard
to crack. *Here:* `backend/app/security.py`.

**Audit trail** — A permanent record of who changed what and when. *Here:* `order_events` with `created_by`.

**Authentication** — Checking who someone is (login). *Here:* `/api/auth/login`.

**Authorization** — Checking what someone may do. *Here:* every account query is scoped to the logged-in user;
roles come in Phase 6.

**Autogenerate (Alembic)** — Alembic compares your models with the database and writes a draft migration. Always read
it before running. *Here:* `flask db migrate`.

**before_request (Flask)** — A function that runs before every request; on a blueprint, before every route in it.
*Here:* the admin role check.

**Blueprint** — A Flask group of related routes that you attach to the app. *Here:* `backend/app/api/*.py`, one
per area (auth, products, cart…).

**Blueprint (Render)** — A `render.yaml` file describing services and their settings, so hosting is set up from code. *Here:* the `kora-api` web service. (Not the same as a Flask blueprint.)

**Boundary testing** — Testing at the exact edge of a rule (day 30, day 30 + 1 minute), where off-by-one bugs
hide. *Here:* `tests/test_returns.py`.

**Business rules as code** — Turning written policy into small, named, tested functions. *Here:* the returns policy in
`backend/app/returns.py`.

**Cascade (ON DELETE CASCADE)** — When a parent row is deleted, its child rows are deleted too. *Here:* deleting an
order deletes its items and events.

**Cash on delivery (COD)** — The customer pays the courier in cash when the parcel arrives. *Here:* `POST /api/checkout/cod`; stock is reserved at once, a phone number is required, and admins mark the cash collected.

**CDN (Content Delivery Network)** — Servers around the world that keep copies of files close to users, so pages and images load fast everywhere. *Here:* Vercel serves the site through its CDN (e.g. the `bom1` Mumbai location, `x-vercel-cache: HIT`).

**CHECK constraint** — A database rule that every row must pass, like `stock >= 0`. *Here:* see `__table_args__` in
the models.

**Checkout Session (Stripe)** — Stripe's record of one checkout attempt, with a hosted payment page URL. *Here:*
created in `backend/app/checkout.py`.

**Circular import** — When file A imports file B and file B imports file A. Python can fail to load either one.
*Here:* avoided by keeping `db` in `backend/app/extensions.py`.

**Client component** — A React component marked `"use client"` that also runs in the browser, so it can use state
and handle clicks. *Here:* `components/shop/filter-panel.tsx`, `components/product/product-view.tsx`.

**CNAME record** — A DNS record that says one name is another name for a second name. *Here:* `kora.abdullahrasheed.tech` is a CNAME to a Vercel name, so Vercel can change its servers without DNS changes.

**Cold start** — The delay when a sleeping service must start before it can answer. *Here:* Render's free instance (~1 minute) and Neon's compute (~1 second).

**Connection pool** — A set of open database connections that the app reuses, because opening a new one is slow.
*Here:* managed by SQLAlchemy; see `pool_pre_ping`.

**Constant-time comparison** — Comparing two secrets in a way that always takes the same time, so timing can't leak
how much matched. *Here:* `hmac.compare_digest` in the sandbox webhook check.

**Constraint** — A rule the database enforces on every write (UNIQUE, NOT NULL, CHECK, FOREIGN KEY).

**Container** — A small, isolated box that runs one program with everything it needs. *Here:* Postgres runs in a
Docker container.

**Content Security Policy (CSP)** — A response header listing where a page may load scripts, styles, images and connections from. *Here:* `frontend/next.config.ts` (site) and `default-src 'none'` on the API.

**Content versioning** — Giving seed content a version number so a live database only gets new text when the version goes up. *Here:* `version` in `policies.json`, applied by `flask policies sync`; admin edits survive until a higher version ships.

**CORS (Cross-Origin Resource Sharing)** — Browser rules for when a page on one domain calls an API on a
different domain. *Here:* we avoid it with the `/api` proxy.

**CORS preflight** — An automatic `OPTIONS` request a browser sends before some cross-site requests (e.g. with JSON), asking the server's permission. *Here:* we never approve cross-site requests, which is one of our CSRF defences.

**Credential stuffing** — Trying email/password pairs leaked from other websites. *Here:* slowed down by per-email rate
limits.

**CSRF (Cross-Site Request Forgery)** — Another website makes your browser send a request to our site, with your
cookies attached. *Here:* blocked by SameSite cookies, the `X-CSRF-TOKEN` header and JSON-only bodies.

**CSRF token (double submit)** — A random value in a readable cookie that the frontend copies into a header. Other
sites can't read it. *Here:* `csrf_access_token` → `X-CSRF-TOKEN`.

**Custom domain** — Your own web address instead of the host's default one. *Here:* `kora.abdullahrasheed.tech` instead of a `vercel.app` address; `FRONTEND_URL` must match it.

**Data migration** — A migration that changes existing rows, not just the structure. *Here:* setting `payment_status` for old orders from their history (`2026_10_20_6c80859c1e35_…`).

**Deadlock** — Two transactions each waiting for a lock the other holds. *Here:* avoided by locking variants in id
order.

**Debounce** — Waiting a short time after the last event before acting, so many quick events become one action.
*Here:* 150 ms before requesting a cart quote.

**deduct_when (Flask-Limiter)** — An option that decides which responses count toward a rate limit. *Here:* only 404s
count for order lookups.

**Delta (stock)** — A change (+10, −1) applied to the current value, instead of a new total. *Here:* admin stock
adjustments.

**DNS (Domain Name System)** — The internet's phone book: it turns a name like `kora.abdullahrasheed.tech` into a server address.

**Docker Compose** — A tool that starts one or more containers from a YAML file. *Here:* `backend/docker-compose.yml`
starts Postgres.

**Double-submit cookie** — A CSRF defence: a readable cookie holds a random token that the page copies into a header; another site can't read the cookie, so it can't send the header. *Here:* `csrf_access_token` → `X-CSRF-TOKEN`.

**Dry run** — Running a command to see what it *would* do, without saving any change. *Here:* `flask images check` runs the sync and then rolls back.

**Eager loading** — Loading related rows together with the main query, instead of later one by one. *Here:*
`selectinload(Product.variants)` in `backend/app/catalog.py`.

**`.env` file** — A local file of environment variables, loaded automatically by `python-dotenv`. Never committed.
*Here:* `backend/.env` (copied from `.env.example`).

**Easing** — The speed curve of an animation: how it speeds up and slows down. *Here:* one curve everywhere, `cubic-bezier(0.22, 1, 0.36, 1)`, fast start, gentle stop, no bounce.

**Enumeration leak** — When different answers let someone find out which values exist (which emails are subscribed, which orders exist). *Here:* the newsletter and order tracking give identical answers.

**Environment variable** — A named value set outside the code (in the OS, a `.env` file, or a hosting dashboard).
*Here:* `DATABASE_URL`, `SECRET_KEY`, etc. See `backend/.env.example`.

**ER diagram (entity-relationship diagram)** — A picture of tables and how they link. *Here:* `docs/guide/01-database.md`.

**EXISTS (SQL)** — A condition that is true if a sub-query returns at least one row. *Here:* the size and colour filter.

**Extension (Flask)** — An add-on package that gives Flask a new feature, like database access. *Here:*
Flask-SQLAlchemy and Flask-Migrate in `backend/app/extensions.py`.

**Facets** — The filter options shown next to results, with only values that actually exist. *Here:* `facets` in
the `/api/products` response.

**Fail fast** — Stop immediately with a clear error when something is wrong, instead of continuing and failing
later in a confusing way. *Here:* `require_env()` in `config.py`.

**Feature flag** — A setting that turns a feature on or off without changing code. *Here:* `NEXT_PUBLIC_ASSISTANT_ENABLED` switches the AI assistant's "Try it" button from "Coming soon".

**Fixture (pytest)** — A function that prepares something a test needs. pytest passes it into tests by name.
*Here:* `app`, `client`, `unreachable_db_client` in `backend/tests/conftest.py`.

**Flask** — A small Python web framework. You write functions and attach URLs to them. *Here:* the whole backend.

**Foreign key (FK)** — A column holding another table's id. The database guarantees the linked row exists.
*Here:* `order_items.order_id` → `orders.id`.

**GIN index** — A Postgres index type that indexes each element inside a value, such as each item of an array. *Here:* `ix_products_tags`, so `tags @> '{new}'` can use an index.

**gunicorn** — A production web server for Python apps. It runs several worker processes. *Here:* will run
`wsgi:app` on Render.

**Gunicorn** — A production WSGI server for Python. *Here:* runs Flask on Render with 1 worker × 4 threads (`backend/gunicorn.conf.py`).

**Hash (password hash)** — A one-way scrambled version of a password. You can check a password against it but can't
turn it back into the password. *Here:* `users.password_hash`.

**Health check** — A URL that reports whether the service is working. Hosting platforms call it automatically.
*Here:* `GET /api/health`.

**HMAC** — A hash made with a secret key; it proves who created a message and that it wasn't changed. *Here:* Stripe
webhook signatures.

**Hosted checkout** — A payment page run by the payment company, not by us. Card data never reaches our servers.

**HSTS (HTTP Strict Transport Security)** — A header telling the browser to use only HTTPS for this site for a set time. *Here:* both apps, two years.

**HTTP status code** — A number in every response that says what happened. 200 = OK, 404 = not found,
405 = method not allowed, 500 = server error, 503 = service unavailable.

**httpOnly cookie** — A cookie that JavaScript can't read. *Here:* `access_token_cookie`.

**Hydration** — React attaching event handlers in the browser to HTML that was rendered on the server.

**Idempotency** — Doing something twice has the same effect as doing it once. *Here:* the webhook handler.

**Idempotency key** — A unique key sent with a request so a retry returns the first result instead of acting again.
*Here:* `checkout-order-<id>` and `refund-order-<id>` sent to Stripe.

**Idempotent** — Safe to run more than once with the same result. *Here:* `flask images sync` (a second run changes nothing), and `flask seed --reset` gives the same data
every time.

**IDOR (Insecure Direct Object Reference)** — Getting someone else's data by changing an id in a request. *Here:*
prevented by filtering on `user_id` in `backend/app/accounts.py`.

**ILIKE** — Postgres case-insensitive pattern matching. `name ILIKE '%linen%'`. *Here:* product search.

**Image manifest** — A file that lists every optimised product photo (name, URL, size). *Here:* `backend/seed/image-manifest.json`, written by `npm run images` and read by `flask images sync`.

**Index (database)** — A sorted lookup structure that makes searching a column fast. *Here:* `ix_orders_email`,
`ix_products_category`.

**Infrastructure as code** — Hosting settings written in files that are reviewed and versioned like code. *Here:* `render.yaml`, `frontend/vercel.json`, `.github/workflows/expire-unpaid.yml`.

**Integer cents** — Storing money as a whole number of cents (`2400` = $24.00) to avoid float rounding errors.
*Here:* every `*_cents` column.

**Interface** — A promise about which methods something has, and their inputs and outputs, without saying how they
work. *Here:* `PaymentProvider`.

**JSON** — A text format for data, like `{"status": "ok"}`. *Here:* every API response.

**JSONB** — A Postgres column type for JSON, stored in a binary format that can be searched and indexed.
*Here:* `return_requests.items`.

**JSON-LD (structured data)** — Hidden JSON in a page that describes it to search engines (product, price,
availability). *Here:* `app/products/[slug]/page.tsx`.

**JWT (JSON Web Token)** — A signed JSON token. Anyone can read it; only the server can create or change it. *Here:*
the session, stored in a cookie.

**Lazy loading** — Downloading an image only when it's about to scroll into view. `next/image` does this by default.

**LazyMotion** — A Motion component that loads only chosen animation features, with the small `m` components, to keep the JavaScript bundle small. *Here:* `components/motion/motion-provider.tsx`.

**LCP (Largest Contentful Paint)** — How long until the biggest thing on the first screen appears; a Core Web
Vitals score. *Here:* the homepage hero, which is preloaded.

**Least privilege** — Give each user only the access they need.

**Lifestyle photo** — A photo of a product being worn or used in a real setting, as opposed to the product on its own. *Here:* `{product-slug}-lifestyle`, shown on card hover and as the second gallery photo.

**Liveness check** — A health check that only asks "is the process running?", without testing dependencies. *Here:* `/api/health/live`, Render's health check, so Neon can sleep.

**Liveness vs readiness** — *Liveness*: "is the process running?" *Readiness*: "can it serve real traffic
(database reachable, etc.)?" *Here:* our health check is a readiness check. See guide 00.

**localStorage** — Browser storage for small amounts of text that stays after the tab closes. *Here:* the cart
(`kora-cart-v1`).

**Logger** — The app's built-in way to write messages to the server logs. Users never see them. *Here:*
`current_app.logger.exception(...)` in `health.py`.

**Lost update** — Two transactions read the same value and both write a result; one write is lost. *Here:* the
oversell bug that row locks prevent.

**Migration** — A versioned script that changes the database structure (adds a table, a column…). *Here:* from
Phase 1, generated by Alembic.

**min-width: auto (CSS grid)** — The default that makes a grid item at least as wide as its content; `min-w-0`
lets it shrink. *Here:* fixed the admin layout on phones.

**Model (ORM model)** — A Python class that represents one database table. *Here:* `backend/app/models/`.

**Motion (library)** — A React animation library (formerly Framer Motion). *Here:* scroll reveals (`components/motion/reveal.tsx`).

**N+1 query problem** — Running 1 query for a list plus 1 more for each item. Slow with real data. *Here:* prevented
with eager loading, and checked by a query-count test.

**Naming convention (constraints)** — A pattern for automatic constraint and index names. *Here:* `NAMING_CONVENTION`
in `backend/app/extensions.py`.

**Neon** — A hosted Postgres service. *Here:* the production database.

**Next.js App Router** — The Next.js routing system where folders in `app/` become URLs. *Here:* `frontend/app/`.

**NOT NULL** — A constraint saying a column must always have a value. In our models, `Mapped[str]` is NOT NULL and
`Mapped[str | None]` allows NULL.

**object-position** — CSS that chooses which part of an image stays visible when it's cropped to a different shape.
*Here:* each photo's `focus` in `frontend/lib/site-images.ts`.

**Offset pagination** — Splitting results into pages with `LIMIT` and `OFFSET`. *Here:* `page` and `per_page`.

**Open redirect** — A link that sends users to any website after login, useful for phishing. *Here:* blocked by
`safeNextPath()` in `frontend/lib/api.ts`.

**Optimistic locking** — Instead of locking, each row has a version number; an update fails if someone else changed the row first, and you retry. *Here:* considered for stock, but we chose row locks.

**ORM (Object-Relational Mapper)** — A library that lets you use Python classes instead of writing SQL by hand.
*Here:* SQLAlchemy.

**PaaS (Platform as a Service)** — A host that runs your code from git and manages servers, HTTPS and restarts for you. *Here:* Render (API) and Vercel (website).

**Padding (images)** — Making an image a new shape by adding strips to its sides, instead of cutting parts off (cropping). *Here:* product photos are padded to 4:5 with the colour sampled from each edge.

**Partial index** — An index that only covers rows matching a condition. *Here:* one default address per user
(`WHERE is_default`).

**Partial prerendering** — A static HTML shell built ahead of time, with live parts streamed in per request. Shown as
`◐` in the build output.

**Partial refund** — Refunding part of a payment. *Here:* refunding only the returned items.

**Payment Intent (Stripe)** — Stripe's record of one payment (`pi_...`). We store it on the order and use it to refund.

**Payment provider** — The service that takes the payment. *Here:* `PAYMENT_PROVIDER=sandbox` or `stripe`.

**Payment status** — Where the money is (`unpaid`, `paid`, `refunded`), kept separate from the order status (where the parcel is). *Here:* `orders.payment_status`; a COD order can be delivered and still unpaid.

**PCI DSS** — Security rules for anyone who handles card data. Hosted checkout keeps us out of most of them.

**Pessimistic locking** — Locking rows before changing them so others must wait (`SELECT … FOR UPDATE`). *Here:* variant rows in the payment webhook and COD checkout, always in id order.

**PgBouncer** — A connection pooler in front of Postgres that lets many clients share a few real connections. *Here:* Neon's `-pooler` endpoint (transaction mode).

**pool_pre_ping** — A SQLAlchemy setting that checks a pooled connection is still alive before using it.
*Here:* `BaseConfig.SQLALCHEMY_ENGINE_OPTIONS` in `config.py`.

**Postgres (PostgreSQL)** — A popular open-source relational database. *Here:* the only database we use, locally
and in production.

**prefers-reduced-motion** — A CSS media feature that is `reduce` when the visitor's system asks for less motion. *Here:* every animation turns into a short fade or nothing.

**Prefetching (Next.js)** — Loading a linked page in the background before the user clicks it. Production only. *Here:*
why login/logout use a full page load.

**preload (next/image)** — Starts downloading an image from the page `<head>`. Use it for the LCP image only. Replaces
the deprecated `priority` prop in Next.js 16.

**Prepared statement** — A query the database compiles once and reuses. It lives on one connection, so it breaks behind a transaction-mode pooler. *Here:* turned off (`prepare_threshold=None`) on Neon's `-pooler` endpoint.

**Primary key (PK)** — The column that uniquely identifies each row. *Here:* `id` in every table.

**Product tag** — A short merchandising label on a product (`new`, `bestseller`, `autumn-edit`) stored in the `products.tags` array. *Here:* drives the homepage sections and `/shop?tag=`.

**Proxy / rewrite** — A server that receives a request and forwards it to another server. *Here:* Next.js
forwards `/api/*` to Flask (`BACKEND_URL`).

**Proxy (Next.js 16)** — Code that runs before a page renders; it was called Middleware before Next.js 16. *Here:*
`frontend/proxy.ts`.

**ProxyFix** — Werkzeug middleware that reads the real client IP from `X-Forwarded-For`, trusting a fixed number of
proxies. *Here:* `create_app()`.

**psycopg** — The Python driver that talks to Postgres. We use version 3. *Here:* the `postgresql+psycopg://`
part of the database URL.

**Pydantic** — A Python library that validates data using type hints. *Here:* `ProductListQuery` in
`backend/app/catalog.py`.

**pytest** — The Python testing tool we use. Run `pytest` in `backend/`.

**Query parameter** — A `key=value` pair after `?` in a URL, used as input to a GET request.

**Race condition** — A bug that happens when two operations run at the same time and the result depends on which
finishes first. *Here:* why order numbers use a sequence, and why stock has a CHECK constraint.

**Rate limiting** — Refusing requests after a limit (status 429). *Here:* Flask-Limiter on login and signup.

**RBAC (role-based access control)** — Permissions given to roles, and roles given to users. *Here:* `customer` and
`admin`.

**Readiness check** — A health check that asks "can this instance do its job now?", e.g. reach the database. *Here:* `/api/health`.

**Refund** — Returning a payment. *Here:* automatic when an order can't be fulfilled.

**Refusal code** — A short, stable, machine-readable reason a rule said no (`final_sale`, `window_closed`). *Here:*
used by the returns page and, later, the AI agent.

**Relationship (SQLAlchemy)** — A Python attribute that follows a foreign key, like `order.items`. *Here:*
`relationship(...)` in the models.

**Render** — A hosting platform. *Here:* will host the Flask backend and the agent.

**Replay attack** — Re-sending an old genuine message. *Here:* blocked by the 5-minute timestamp check on webhooks.

**REST** — An API style where URLs name resources and HTTP methods say what to do (GET reads).

**Return request** — A customer's request to send items back for a refund or an exchange. *Here:* the
`return_requests` table, status `requested`.

**Reverse proxy** — A server that receives requests and passes them to another server behind it. *Here:* Next.js forwards `/api/*` to Flask; Render's load balancer sits in front of gunicorn.

**Rewrite (Next.js)** — A rule that forwards a URL to another server without the browser knowing. *Here:* `/api/*` →
Flask in `frontend/next.config.ts`.

**Route** — A URL plus HTTP method connected to a Python function. *Here:* `@bp.get("/health")`.

**Router cache (Next.js)** — The client-side memory of pages already loaded or prefetched, reused for fast navigation.

**Row lock (SELECT ... FOR UPDATE)** — Reading rows and locking them until the transaction ends. *Here:* orders and
variants in the webhook.

**Salt** — Random bytes mixed into each password hash, so the same password gives different hashes.

**SameSite** — A cookie setting that controls whether it's sent on requests started by other websites. *Here:* `Lax`.

**Sandbox (payments)** — A pretend payment system with test cards and no real money. *Here:* our own provider,
built because Stripe isn't available in Pakistan; its page is `/pay/sandbox/[sessionId]`.

**Scroll snap** — CSS that makes a scrolling list stop neatly on an item instead of anywhere. *Here:* the "New for autumn" row (`snap-x snap-mandatory`).

**Secure (cookie)** — A cookie setting: only send over HTTPS. *Here:* on in production.

**Seed data** — Starting data loaded into an empty database. *Here:* `backend/seed/*.json` and `flask seed`.

**Self-deadlock** — A worker waiting for a reply that only it could give, so it waits forever. *Here:* why the
sandbox delivers its webhook in-process.

**Sequence (Postgres)** — A database counter that hands out each number once, even under concurrent requests.
*Here:* `order_number_seq` for KO-1001, KO-1002…

**Server component** — A React component that runs only on the server and sends HTML, never JavaScript. The default
in the App Router.

**server-only** — A package that makes the build fail if a client component imports a server file. *Here:*
`frontend/lib/api-server.ts`.

**Service layer** — Functions that hold the business and query logic, separate from HTTP routes. *Here:*
`backend/app/catalog.py`.

**Session** — How a server remembers who you are across requests. *Here:* a JWT in a cookie.

**Shared rate limit** — One counter used by several endpoints. *Here:* tracking and returns share one lookup budget.

**sharp** — A fast Node.js image library for resizing and converting. *Here:* `frontend/scripts/optimize-images.mjs`.

**Side channel** — Information leaked by something other than the message: status codes, response size, timing.

**sizes / srcset** — `srcset` lists the same image at several widths; `sizes` tells the browser how wide it will be
on screen, so it can pick the smallest good-enough file.

**Skeleton** — A grey placeholder shaped like the content that is loading. *Here:* `components/skeletons.tsx`.

**SKIP LOCKED** — Skip rows another transaction has locked instead of waiting. *Here:* the expiry job.

**SKU (Stock Keeping Unit)** — A unique code for one sellable item. *Here:* `KO-001-WHIT-M` = tee, white, size M.

**Slug** — A URL-friendly name: lowercase, with hyphens. *Here:* `everyday-cotton-tee`, `gift-cards`.

**Snapshot** — A copy of data taken at one moment so later changes don't affect it. *Here:* product name, price and
final-sale flag on `order_items`.

**Soft 404** — A "not found" page sent with status 200. Next.js adds `noindex` so search engines skip it. *Here:* unknown
product URLs (because the response is streamed).

**SQLAlchemy** — The Python ORM and database toolkit we use. *Here:* `db` in `extensions.py`.

**sslmode** — A Postgres connection setting for TLS encryption; `require` means never connect unencrypted. *Here:* required for remote databases in production.

**@starting-style** — A CSS rule that gives an element's style at the moment it appears, so a transition can run from it (e.g. from off-screen). *Here:* the cart drawer slides in from the right.

**State machine** — A set of states and the allowed moves between them. *Here:* `ORDER_TRANSITIONS` and
`RETURN_TRANSITIONS` in `backend/app/admin.py`.

**Streaming** — Sending a page in pieces as each part becomes ready, instead of waiting for all of it.

**StrEnum** — A Python enum whose members are also strings. *Here:* `OrderStatus` in `backend/app/models/types.py`.

**Stripe CLI** — A command-line tool that forwards webhooks to your laptop (`stripe listen`) and triggers test events.

**stripe-mock** — Stripe's official fake API server that checks requests against the real API schema. Used for
offline end-to-end tests.

**Support ticket** — A customer request for human help. *Here:* `support_tickets`, created by `/contact` and later
the agent.

**Suspense** — A React component that shows a fallback while its children load. *Here:* around every data-fetching
part of a page.

**Tailwind CSS** — A CSS framework of small utility classes (`px-4`, `text-sm`). Brand colours are defined in
`frontend/app/globals.css`.

**Test card** — A card number a payment sandbox accepts without real money. *Here:* 4242 4242 4242 4242 succeeds,
4000 0000 0000 0002 is declined.

**Test mode (Stripe)** — Stripe's sandbox: test keys (`sk_test_...`) and test cards, no real money.

**Test-driven development (TDD)** — Writing a test for a rule first, then the code that makes it pass.

**Tie-breaker (sorting)** — An extra unique sort key so rows that tie always come out in the same order. *Here:*
`Product.id` at the end of every sort.

**TIMESTAMPTZ** — A Postgres timestamp stored in UTC with time zone awareness. *Here:* every `created_at`.

**Timing attack** — Learning a secret by measuring how long the server takes to answer. *Here:* prevented by
constant-time comparison.

**TLS (Transport Layer Security)** — The encryption behind HTTPS and secure database connections. *Here:* HTTPS everywhere, and `sslmode=require` between Render and Neon.

**Transaction** — A group of database changes that succeed or fail together (all or nothing). *Here:* the whole seed
is one transaction.

**TRUNCATE** — A fast SQL command that empties a table. *Here:* `flask seed --reset`.

**UNIQUE constraint** — A rule that no two rows can have the same value in a column. *Here:* `users.email`,
`products.slug`, `product_variants.sku`.

**Upsert** — *Update* a row if it exists, *insert* it if not. *Here:* `flask images sync` upserts one `product_images` row per photo, found by its URL.

**useId (React)** — A hook that creates a unique id per component instance, for linking labels to inputs. *Here:*
form fields that can appear on two pages at once.

**User enumeration** — Finding out which emails have accounts from an app's responses or timing. *Here:* prevented at
login by identical responses and a dummy hash check.

**useSyncExternalStore** — A React hook for reading data stored outside React (like localStorage) safely. *Here:*
the cart.

**useTransition** — A React hook that marks an update as non-urgent and gives an `isPending` flag. *Here:* the filter
panel's loading state.

**uv** — A fast tool that installs Python versions, creates virtual environments and installs packages. *Here:*
installed Python 3.12 and created `backend/.venv`.

**Validation error (400)** — The response for input that breaks the rules. *Here:* `{"error": {"code":
"validation_error", ...}}`.

**Variant** — One buyable version of a product (a size and color), with its own stock. *Here:* `product_variants`.

**Vercel** — A hosting platform for Next.js sites. *Here:* will host the frontend.

**Virtual environment (venv)** — A private folder of Python packages for one project. *Here:* `backend/.venv`;
activate it with `source .venv/bin/activate`.

**Volume (Docker)** — Storage that keeps a container's data after the container stops. *Here:* `kora_pg` keeps
the Postgres data.

**Webhook** — An HTTP request one server sends to another when something happens. *Here:* Stripe →
`/api/stripe/webhook`.

**Webhook signing secret** — The shared secret (`whsec_...`) used to verify webhook signatures.

**WebP** — A modern image format, usually 25–35% smaller than JPEG at the same visible quality. *Here:* every site
photo in `frontend/public/images/`.

**Worker (gunicorn)** — A separate server process handling requests; workers don't share memory. Threads inside one worker do. *Here:* `WEB_CONCURRENCY=1`.

**WSGI (Web Server Gateway Interface)** — The standard way Python web apps and web servers talk to each other.
*Here:* `backend/wsgi.py` exposes `app` for `flask run` and gunicorn.

**XSS (Cross-Site Scripting)** — Attacker JavaScript running inside our page. *Here:* why the session cookie is
httpOnly.
