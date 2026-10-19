# Glossary

Technical terms used in this project, in alphabetical order. Each entry says what the term means in plain English
and where it appears in Kora Outfitters.

---

**12-factor app** — A well-known list of rules for building web apps that are easy to deploy. One rule: keep
config in environment variables, not in code. *Here:* `backend/app/config.py`.

**415 Unsupported Media Type** — The response when a request body isn't in a format the server accepts. *Here:*
anything that isn't JSON.

**429 Too Many Requests** — The response when a rate limit is hit. Comes with a `Retry-After` header.

**AbortController** — A browser API for cancelling a `fetch` request. *Here:* cancelling an outdated cart quote.

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

**Authentication** — Checking who someone is (login). *Here:* `/api/auth/login`.

**Authorization** — Checking what someone may do. *Here:* every account query is scoped to the logged-in user;
roles come in Phase 6.

**Autogenerate (Alembic)** — Alembic compares your models with the database and writes a draft migration. Always read
it before running. *Here:* `flask db migrate`.

**Blueprint** — A Flask group of related routes that you attach to the app. *Here:* `backend/app/api/*.py`, one
per area (auth, products, cart…).

**Cascade (ON DELETE CASCADE)** — When a parent row is deleted, its child rows are deleted too. *Here:* deleting an
order deletes its items and events.

**CHECK constraint** — A database rule that every row must pass, like `stock >= 0`. *Here:* see `__table_args__` in
the models.

**Circular import** — When file A imports file B and file B imports file A. Python can fail to load either one.
*Here:* avoided by keeping `db` in `backend/app/extensions.py`.

**Client component** — A React component marked `"use client"` that also runs in the browser, so it can use state
and handle clicks. *Here:* `components/shop/filter-panel.tsx`, `components/product/product-view.tsx`.

**Connection pool** — A set of open database connections that the app reuses, because opening a new one is slow.
*Here:* managed by SQLAlchemy; see `pool_pre_ping`.

**Constraint** — A rule the database enforces on every write (UNIQUE, NOT NULL, CHECK, FOREIGN KEY).

**Container** — A small, isolated box that runs one program with everything it needs. *Here:* Postgres runs in a
Docker container.

**CORS (Cross-Origin Resource Sharing)** — Browser rules for when a page on one domain calls an API on a
different domain. *Here:* we avoid it with the `/api` proxy.

**Credential stuffing** — Trying email/password pairs leaked from other websites. *Here:* slowed down by per-email rate
limits.

**CSRF (Cross-Site Request Forgery)** — Another website makes your browser send a request to our site, with your
cookies attached. *Here:* blocked by SameSite cookies, the `X-CSRF-TOKEN` header and JSON-only bodies.

**CSRF token (double submit)** — A random value in a readable cookie that the frontend copies into a header. Other
sites can't read it. *Here:* `csrf_access_token` → `X-CSRF-TOKEN`.

**Debounce** — Waiting a short time after the last event before acting, so many quick events become one action.
*Here:* 150 ms before requesting a cart quote.

**Docker Compose** — A tool that starts one or more containers from a YAML file. *Here:* `backend/docker-compose.yml`
starts Postgres.

**Eager loading** — Loading related rows together with the main query, instead of later one by one. *Here:*
`selectinload(Product.variants)` in `backend/app/catalog.py`.

**`.env` file** — A local file of environment variables, loaded automatically by `python-dotenv`. Never committed.
*Here:* `backend/.env` (copied from `.env.example`).

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

**Fixture (pytest)** — A function that prepares something a test needs. pytest passes it into tests by name.
*Here:* `app`, `client`, `unreachable_db_client` in `backend/tests/conftest.py`.

**Flask** — A small Python web framework. You write functions and attach URLs to them. *Here:* the whole backend.

**Foreign key (FK)** — A column holding another table's id. The database guarantees the linked row exists.
*Here:* `order_items.order_id` → `orders.id`.

**gunicorn** — A production web server for Python apps. It runs several worker processes. *Here:* will run
`wsgi:app` on Render.

**Hash (password hash)** — A one-way scrambled version of a password. You can check a password against it but can't
turn it back into the password. *Here:* `users.password_hash`.

**Health check** — A URL that reports whether the service is working. Hosting platforms call it automatically.
*Here:* `GET /api/health`.

**HTTP status code** — A number in every response that says what happened. 200 = OK, 404 = not found,
405 = method not allowed, 500 = server error, 503 = service unavailable.

**httpOnly cookie** — A cookie that JavaScript can't read. *Here:* `access_token_cookie`.

**Hydration** — React attaching event handlers in the browser to HTML that was rendered on the server.

**Idempotent** — Safe to run more than once with the same result. *Here:* `flask seed --reset` gives the same data
every time.

**IDOR (Insecure Direct Object Reference)** — Getting someone else's data by changing an id in a request. *Here:*
prevented by filtering on `user_id` in `backend/app/accounts.py`.

**ILIKE** — Postgres case-insensitive pattern matching. `name ILIKE '%linen%'`. *Here:* product search.

**Index (database)** — A sorted lookup structure that makes searching a column fast. *Here:* `ix_orders_email`,
`ix_products_category`.

**Integer cents** — Storing money as a whole number of cents (`2400` = $24.00) to avoid float rounding errors.
*Here:* every `*_cents` column.

**JSON** — A text format for data, like `{"status": "ok"}`. *Here:* every API response.

**JSONB** — A Postgres column type for JSON, stored in a binary format that can be searched and indexed.
*Here:* `return_requests.items`.

**JSON-LD (structured data)** — Hidden JSON in a page that describes it to search engines (product, price,
availability). *Here:* `app/products/[slug]/page.tsx`.

**JWT (JSON Web Token)** — A signed JSON token. Anyone can read it; only the server can create or change it. *Here:*
the session, stored in a cookie.

**Liveness vs readiness** — *Liveness*: "is the process running?" *Readiness*: "can it serve real traffic
(database reachable, etc.)?" *Here:* our health check is a readiness check. See guide 00.

**localStorage** — Browser storage for small amounts of text that stays after the tab closes. *Here:* the cart
(`kora-cart-v1`).

**Logger** — The app's built-in way to write messages to the server logs. Users never see them. *Here:*
`current_app.logger.exception(...)` in `health.py`.

**Migration** — A versioned script that changes the database structure (adds a table, a column…). *Here:* from
Phase 1, generated by Alembic.

**Model (ORM model)** — A Python class that represents one database table. *Here:* `backend/app/models/`.

**N+1 query problem** — Running 1 query for a list plus 1 more for each item. Slow with real data. *Here:* prevented
with eager loading, and checked by a query-count test.

**Naming convention (constraints)** — A pattern for automatic constraint and index names. *Here:* `NAMING_CONVENTION`
in `backend/app/extensions.py`.

**Neon** — A hosted Postgres service. *Here:* the production database.

**Next.js App Router** — The Next.js routing system where folders in `app/` become URLs. *Here:* `frontend/app/`.

**NOT NULL** — A constraint saying a column must always have a value. In our models, `Mapped[str]` is NOT NULL and
`Mapped[str | None]` allows NULL.

**Offset pagination** — Splitting results into pages with `LIMIT` and `OFFSET`. *Here:* `page` and `per_page`.

**Open redirect** — A link that sends users to any website after login, useful for phishing. *Here:* blocked by
`safeNextPath()` in `frontend/lib/api.ts`.

**ORM (Object-Relational Mapper)** — A library that lets you use Python classes instead of writing SQL by hand.
*Here:* SQLAlchemy.

**Partial index** — An index that only covers rows matching a condition. *Here:* one default address per user
(`WHERE is_default`).

**Partial prerendering** — A static HTML shell built ahead of time, with live parts streamed in per request. Shown as
`◐` in the build output.

**pool_pre_ping** — A SQLAlchemy setting that checks a pooled connection is still alive before using it.
*Here:* `BaseConfig.SQLALCHEMY_ENGINE_OPTIONS` in `config.py`.

**Postgres (PostgreSQL)** — A popular open-source relational database. *Here:* the only database we use, locally
and in production.

**Primary key (PK)** — The column that uniquely identifies each row. *Here:* `id` in every table.

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

**Relationship (SQLAlchemy)** — A Python attribute that follows a foreign key, like `order.items`. *Here:*
`relationship(...)` in the models.

**Render** — A hosting platform. *Here:* will host the Flask backend and the agent.

**REST** — An API style where URLs name resources and HTTP methods say what to do (GET reads).

**Rewrite (Next.js)** — A rule that forwards a URL to another server without the browser knowing. *Here:* `/api/*` →
Flask in `frontend/next.config.ts`.

**Route** — A URL plus HTTP method connected to a Python function. *Here:* `@bp.get("/health")`.

**Salt** — Random bytes mixed into each password hash, so the same password gives different hashes.

**SameSite** — A cookie setting that controls whether it's sent on requests started by other websites. *Here:* `Lax`.

**Secure (cookie)** — A cookie setting: only send over HTTPS. *Here:* on in production.

**Seed data** — Starting data loaded into an empty database. *Here:* `backend/seed/*.json` and `flask seed`.

**Sequence (Postgres)** — A database counter that hands out each number once, even under concurrent requests.
*Here:* `order_number_seq` for KO-1001, KO-1002…

**Server component** — A React component that runs only on the server and sends HTML, never JavaScript. The default
in the App Router.

**server-only** — A package that makes the build fail if a client component imports a server file. *Here:*
`frontend/lib/api-server.ts`.

**Service layer** — Functions that hold the business and query logic, separate from HTTP routes. *Here:*
`backend/app/catalog.py`.

**Session** — How a server remembers who you are across requests. *Here:* a JWT in a cookie.

**Skeleton** — A grey placeholder shaped like the content that is loading. *Here:* `components/skeletons.tsx`.

**SKU (Stock Keeping Unit)** — A unique code for one sellable item. *Here:* `KO-001-WHIT-M` = tee, white, size M.

**Slug** — A URL-friendly name: lowercase, with hyphens. *Here:* `everyday-cotton-tee`, `gift-cards`.

**Snapshot** — A copy of data taken at one moment so later changes don't affect it. *Here:* product name, price and
final-sale flag on `order_items`.

**Soft 404** — A "not found" page sent with status 200. Next.js adds `noindex` so search engines skip it. *Here:* unknown
product URLs (because the response is streamed).

**SQLAlchemy** — The Python ORM and database toolkit we use. *Here:* `db` in `extensions.py`.

**Streaming** — Sending a page in pieces as each part becomes ready, instead of waiting for all of it.

**StrEnum** — A Python enum whose members are also strings. *Here:* `OrderStatus` in `backend/app/models/types.py`.

**Suspense** — A React component that shows a fallback while its children load. *Here:* around every data-fetching
part of a page.

**Tailwind CSS** — A CSS framework of small utility classes (`px-4`, `text-sm`). Brand colours are defined in
`frontend/app/globals.css`.

**Tie-breaker (sorting)** — An extra unique sort key so rows that tie always come out in the same order. *Here:*
`Product.id` at the end of every sort.

**TIMESTAMPTZ** — A Postgres timestamp stored in UTC with time zone awareness. *Here:* every `created_at`.

**Transaction** — A group of database changes that succeed or fail together (all or nothing). *Here:* the whole seed
is one transaction.

**TRUNCATE** — A fast SQL command that empties a table. *Here:* `flask seed --reset`.

**UNIQUE constraint** — A rule that no two rows can have the same value in a column. *Here:* `users.email`,
`products.slug`, `product_variants.sku`.

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

**WSGI (Web Server Gateway Interface)** — The standard way Python web apps and web servers talk to each other.
*Here:* `backend/wsgi.py` exposes `app` for `flask run` and gunicorn.

**XSS (Cross-Site Scripting)** — Attacker JavaScript running inside our page. *Here:* why the session cookie is
httpOnly.
