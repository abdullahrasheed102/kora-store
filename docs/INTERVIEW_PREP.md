# Interview Prep

Questions an interviewer might ask about this project, with model answers. Say the answers in your own words.
Point to real files when you can; it shows you know the code.

---

## Phase 0 — Project setup

### 1. What is the application factory pattern, and why did you use it?

**Answer:** Instead of creating the Flask app at the top of a file, I create it inside a function,
`create_app()` (`backend/app/__init__.py`). The function loads config, attaches extensions like SQLAlchemy,
registers error handlers and blueprints, then returns the app. The main benefit is testing. My tests call
`create_app(TestingConfig())` to get an app that uses a separate test database. One test even builds an app
pointed at a closed port to check what happens when the database is down. With a global app, importing the
module would read secrets and connect right away, and every test would share one configuration.

### 2. How does your app handle configuration and secrets?

**Answer:** All config comes from environment variables, following the 12-factor app idea. `config.py` reads
them when the config object is created. Locally they come from a `.env` file that git ignores. On Render they're
set in the dashboard. `.env.example` is committed so a new developer can see every variable. Required values
like `SECRET_KEY` and `DATABASE_URL` fail fast: the app won't start without them. `APP_ENV` defaults to
`production`, so forgetting it can't switch debug mode on by accident.

### 3. What are blueprints?

**Answer:** A blueprint is a group of related routes. I have one per area: `auth`, `products`, `cart`,
`checkout`, `orders`, `admin`, `agent` and `health`. The factory registers all of them under `/api`. This keeps
files small and focused, and it makes it easy to see where any endpoint lives. The `agent` blueprint is separate
on purpose: it will use API-key auth instead of user cookies.

### 4. What does your health check do, and what are the trade-offs?

**Answer:** `GET /api/health` runs `SELECT 1`. If it works, it returns 200 with `"database": "ok"`. If it fails,
it returns 503 with `"database": "unavailable"`. I catch only `SQLAlchemyError`, not every exception, so a bug in
my own code shows up as a real 500 and isn't mistaken for a database outage. The real error goes to the logs, not
the response, because it contains the database host and username. The trade-off is liveness vs readiness: Render
uses this check to decide if a deploy is healthy, so a short database problem could make Render think the app
itself is broken. Some teams split this into two endpoints: a liveness check that only says "the process is up",
and a readiness check that also tests dependencies.

### 5. Why Postgres in Docker locally, and not SQLite?

**Answer:** Production uses Postgres on Neon, and I want local behaviour to match it. SQLite is different in ways
that matter for this project. It handles row locks differently, and I'll need row locks to decrement stock safely
when two people buy the last item at the same time. It also treats types and constraints more loosely, so a bug
could pass locally and fail in production. Docker Compose runs real Postgres with one command, and tests use a
separate `kora_test` database so they can delete data safely.

### 6. Why do all API errors return the same JSON shape?

**Answer:** Flask returns HTML error pages by default, but my clients are a Next.js frontend and an AI agent.
Both need to read errors as data. Every error returns `{"error": {"code": "...", "message": "..."}}` with the
right HTTP status. The `code` is a stable machine-readable string like `not_found` or `out_of_stock`, so the
frontend can show the right message and the agent can decide what to do. Unexpected crashes return a generic 500
message, so stack traces never leak.

### 7. What is `pool_pre_ping` and why do you need it?

**Answer:** SQLAlchemy keeps a pool of open database connections and reuses them, because opening a new
connection is slow. Neon closes connections that are idle for a while, and Render's free plan puts the app to
sleep. Without pre-ping, the first request after a quiet period could get a dead connection and fail. Pre-ping
runs a tiny check before handing out a connection, and replaces it if it's dead. It costs one quick round trip,
which is worth it for reliability.

### 8. Why does the frontend proxy `/api` to the backend instead of calling it directly?

**Answer:** The frontend is on Vercel and the backend on Render, which are two different domains. If the browser
called Render directly, I'd need CORS configuration, and my auth cookie would be a third-party cookie, which many
browsers block or restrict. So Next.js rewrites every `/api/*` request to the Flask URL on the server side. The
browser only ever sees one domain, the cookie stays first-party, and CORS never comes up.

---

## Phase 1 — Database, models and seed

### 1. Why do you store money as integer cents?

**Answer:** Floats can't represent most decimal values exactly. In Python, `0.1 + 0.2` is
`0.30000000000000004`, and those tiny errors add up across many orders and refunds. So every amount is an integer
number of cents: `price_cents = 2400` is $24.00. Adding and multiplying integers is always exact, and Stripe's API
also uses integer cents, so there's no conversion at checkout. I only format it as dollars when showing it to a
person. The database also has a check constraint, `total_cents = subtotal_cents + shipping_cents`, so a total can
never disagree with its parts.

### 2. Why does `order_items` copy the product name and price instead of linking to the product?

**Answer:** An order is a historical record. If I change a tee's price from $24 to $28 next month, a customer's old
order must still say $24, because that's what they paid. The same goes for the final-sale flag: the return rules in
Phase 5 must use what was true at purchase time. So each order item stores a snapshot: name, size, color, unit price
and final-sale flag. It still keeps a `variant_id` foreign key for stock updates and links, with `ON DELETE SET NULL`,
because the snapshot is enough on its own. The shipping address is copied onto the order for the same reason.

### 3. Your models already validate data in Python. Why add database constraints too?

**Answer:** Python validation only protects code paths that go through it. Raw SQL, admin scripts, a future bug, or
two requests racing each other can all skip it. Database constraints are checked on every single write. So I put the
critical rules in Postgres: `CHECK (stock >= 0)` is the last line of defence against overselling, `UNIQUE` on
emails, SKUs and order numbers, `CHECK (email = lower(email))`, and a partial unique index so a user has at most one
default address. Python gives the friendly error message; the database guarantees the rule. My tests run raw SQL
updates to prove the constraints actually fire.

### 4. How do you generate order numbers like KO-1001, and why not `MAX(id) + 1`?

**Answer:** From a Postgres sequence. The column default is `'KO-' || nextval('order_number_seq')`, and the sequence
starts at 1001. A sequence hands out each value exactly once, even when two checkouts insert at the same moment.
`SELECT MAX() + 1` has a race condition: two requests can read the same maximum and both try to use the next number.
One subtle point: the seed inserts KO-1001 to KO-1012 with explicit numbers, so the sequence never hands those out.
After seeding I call `setval` to move it past 1012, otherwise the first real order would collide with KO-1001.

### 5. What is a migration, and what did you learn from autogenerating one?

**Answer:** A migration is a versioned script that changes the database schema, with an `upgrade` and a
`downgrade`. They're in git, so the laptop, CI and Neon are all built the same way. Alembic can autogenerate one by
comparing my models with the database, but it's a draft, not the final answer. In my first migration, autogenerate
missed the standalone sequence for order numbers, and it wrote each enum check constraint twice with the same name,
which would have failed. I fixed both by hand. My tests build the test database by running the real migrations, and
one test uses Alembic's `compare_metadata` to fail if the models and migrations ever drift apart.

### 6. Why store enums like order status as VARCHAR with a CHECK constraint, not a Postgres ENUM type?

**Answer:** Both stop invalid values. The difference is how easy they are to change. Adding a value to a native
Postgres ENUM needs `ALTER TYPE ... ADD VALUE`, which has restrictions inside transactions, and removing a value is
much harder. With VARCHAR plus a CHECK constraint, a change is an ordinary migration that drops and recreates the
check. In Python I use `StrEnum`, so `OrderStatus.SHIPPED` is also the plain string `"shipped"`, and it turns into
JSON without conversion.

### 7. How does the seed keep demo data from going stale?

**Answer:** The JSON stores relative dates: `created_days_ago`, `delivered_days_ago`, `estimated_delivery_in_days`.
At seed time I convert them using the current time, so an order delivered "10 days ago" is always 10 days old,
whenever the seed runs. That matters for the return rules: KO-1007 is always outside the 30-day window and KO-1005
always inside it. The seed also computes prices from the catalog and shipping from the same `pricing.py` function
the cart uses, and builds a timeline of `order_events` for each order. A validation step refuses any timeline that's
impossible, like delivered before shipped. `now` is a parameter, so tests pass a fixed date and check exact values.

### 8. What indexes did you add, and how did you choose them?

**Answer:** Primary keys and UNIQUE columns get indexes automatically: slug, SKU, email, order number. I also
indexed foreign keys (`order_items.order_id`, `product_variants.product_id`), because Postgres does not index them
automatically and every join uses them. Then I indexed the columns we filter on: `products.category` for the shop,
`orders.email` for order tracking, `orders.status` for the admin filters, and a combined index on
`order_events (order_id, created_at)`, because the timeline is always "events for one order, sorted by time".
Each index makes writes slightly slower, so I only add them for real queries.

---

## Phase 2 — Catalog API and storefront

### 1. What is the N+1 query problem, and how did you prevent it?

**Answer:** It happens when you load a list with one query and then the ORM runs one more query per item to load a
relationship. For 12 products that's 13 queries, and it grows with the page size. With an ORM it's easy to miss
because `product.variants` looks like a normal attribute. I used `selectinload(Product.variants)`, which loads the
variants for every product on the page in one extra `WHERE product_id IN (...)` query. To make sure it stays fixed, I
wrote a test that attaches a SQLAlchemy event listener, counts the SQL statements for a page of 2 and a page of 20,
and asserts they're equal.

### 2. How do you validate query parameters, and why does it matter?

**Answer:** With a Pydantic model, `ProductListQuery`. Each field has a type and limits: `page >= 1`, `per_page`
between 1 and 48, `sort` is one of five allowed values, and `min_price` can't be greater than `max_price`. A small
helper reads Flask's query args into the model, turning repeated keys like `?size=S&size=M` into lists. Invalid input
returns a 400 with code `validation_error` and a message that names the field. It matters for correctness, so
`page=abc` doesn't become a 500 error, and for safety: without the `per_page` cap, one request could ask for
millions of rows.

### 3. How does the size and colour filter work in SQL?

**Answer:** It's a single `EXISTS` sub-query on `product_variants`, linked to the outer product, with `stock > 0`,
`size IN (...)` and `color IN (...)` together. Putting them in the same `EXISTS` means one variant has to satisfy
all the conditions. If I'd written two separate checks, a product with "M in White" and "L in Black" would wrongly
match "M in Black". I also only match in-stock variants, because a shopper filtering by size wants something they
can actually buy. There's a test with exactly that tricky product.

### 4. Why does every sort order end with the product id?

**Answer:** SQL doesn't guarantee any order for rows that tie on the sort key. If two products cost the same, Postgres
can return them in a different order on different queries. With offset pagination, that means a product can appear
on page 1 and again on page 2, while another is skipped. Adding `Product.id` as the last sort key makes the order
deterministic. A test checks that pages 1 and 2 don't overlap.

### 5. Offset or cursor pagination: which did you use and why?

**Answer:** Offset pagination, `LIMIT 12 OFFSET 12` for page 2, because it's simple and supports numbered pages,
which a shop grid needs. Its weaknesses are that large offsets get slower, since the database still walks past the
skipped rows, and that items can shift if data changes between page loads. Cursor (keyset) pagination fixes both by
asking for "items after this id", which suits infinite scroll and very large tables. For a catalog of 20 products,
offset is the right trade-off.

### 6. Explain server components vs client components in your storefront.

**Answer:** Server components run only on the server. They fetch data and send HTML, and their code never reaches the
browser. Pages, the product grid, the header and the footer are server components. Client components, marked
`"use client"`, also run in the browser, so they can use state and event handlers. I only use them where the user
interacts: the filter panel, the sort dropdown, the mobile menu and the colour/size picker. That keeps the JavaScript
bundle small and the pages fast. The data is fetched on the server and passed to the client components as props.

### 7. How does a page render with Cache Components and Suspense?

**Answer:** At build time, Next.js prerenders everything that doesn't need request data (the layout, header, footer
and headings) into a static shell. Anything that reads `params` or `searchParams`, or does an uncached fetch, has to
sit inside a `<Suspense>` boundary. The shell is sent immediately with skeletons in those places, and the real content
streams in when the API answers. For a shop this gives two benefits: stock is always live because product data isn't
cached, and the build never calls the API, so it works on Vercel even when the backend isn't reachable. The
trade-off is that a missing product returns a "soft 404": status 200 with the 404 page and a `noindex` tag, because
the response had already started.

### 8. Why are the shop filters stored in the URL?

**Answer:** Because the URL is the shareable state of the page. `/shop/tops?size=M&sort=price_asc` can be
bookmarked, shared or opened in a new tab, the back button undoes a filter change, and search engines see real URLs.
The filter panel keeps no state: each change builds a new URL with a helper and navigates there, and the server
renders the matching products. I wrap the navigation in `useTransition` so the panel shows a pending state, and the
active-filter chips are plain links, so removing a filter works even before JavaScript loads.

---

## Phase 3 — Cart and accounts

### 1. How do you make sure customers can't change prices?

**Answer:** The browser never sends prices. The cart in localStorage holds only variant ids and quantities. Every
time it changes, the frontend calls `/cart/quote`, and Flask loads each variant from Postgres, uses the database
price, checks stock, applies the shipping rules from one shared `pricing.py` module and returns the totals. If a
tampered request includes a `price_cents` field, Pydantic drops it (`extra="ignore"`), and there's a test proving the
total uses the database price. Checkout in Phase 4 calls the same function again, so the amount charged is always
computed on the server.

### 2. Why store the JWT in an httpOnly cookie instead of localStorage?

**Answer:** Because of XSS. If an attacker ever gets JavaScript to run in our page, it can read everything in
localStorage, including a token, and use it from their own machine. An httpOnly cookie can't be read by JavaScript at
all: the browser just attaches it to requests. The cost of cookies is CSRF, because the browser also attaches them
when another site makes the request. So I combine the httpOnly cookie with SameSite=Lax, the Secure flag in
production, and a CSRF token.

### 3. Explain your CSRF protection.

**Answer:** Two layers. First, the session cookie is SameSite=Lax, so browsers don't attach it to cross-site POSTs
at all. Second, the double-submit pattern from Flask-JWT-Extended: at login the server sets a second, readable cookie
with a random CSRF value, and the JWT contains the same value. For every POST, PUT, PATCH or DELETE, the frontend
reads that cookie and sends it in an `X-CSRF-TOKEN` header, and the server checks it matches the JWT. Another site
can make the victim's browser send our cookies, but it can't read them, so it can't produce the header. For signup
and login, where there's no session yet, I only accept `application/json`: a cross-site HTML form can't send JSON, and
a cross-site fetch with JSON needs a CORS preflight that we never approve.

### 4. How do you prevent attackers from finding out which emails have accounts?

**Answer:** At login, an unknown email and a wrong password return exactly the same 401 with the same message.
Timing is the subtle part: checking an argon2 hash takes tens of milliseconds, so if unknown emails returned
instantly, an attacker could tell the difference by timing. When the email doesn't exist, I still verify the password
against a dummy hash, so both paths do the same work. Signup is the honest exception: it says the email is taken,
like most shops, because hiding it properly needs email verification. I limit the damage with a rate limit on signup.

### 5. How is login rate limited, and why two limits?

**Answer:** With Flask-Limiter. Per IP: 5 attempts a minute and 30 an hour, which stops one machine guessing quickly.
Per email: 10 an hour whichever IP the attempts come from, which stops a distributed attack on one account using many
IPs. I chose limits instead of account lockout, because lockout lets an attacker lock a real customer out on purpose.
Two production details matter. Behind Vercel and Render, the client IP is in `X-Forwarded-For`, so I use ProxyFix
configured with the exact number of proxies; trusting more would let clients fake their IP. And with several gunicorn
workers, the counters must be in Redis, not in memory.

### 6. What is IDOR and how did you prevent it?

**Answer:** Insecure Direct Object Reference: changing an id in a URL, like `/addresses/43`, and getting another
user's data because the server didn't check ownership. Every account query includes the owner in the WHERE clause:
`Address.id == id AND Address.user_id == current_user.id`. A wrong owner simply finds nothing and gets a 404, which
also doesn't confirm the id exists. A related decision: account order history links orders by `user_id`, never by
email. We don't verify emails, so if we matched guest orders by email, anyone could sign up with your address and read
your orders. Both cases have tests.

### 7. How does the cart stay correct when the user clicks quickly?

**Answer:** Two techniques in the cart provider. A 150 ms debounce: each change starts a timer, and a new change
cancels the old timer, so five quick clicks become one request. And an AbortController: when the cart changes, the
previous request is aborted, so a slow old response can never arrive late and overwrite newer totals. That's a race
condition fixed on the client. Each quote also stores which cart it was computed for, so the UI knows when totals are
outdated and dims them until the fresh quote arrives.

### 8. Why use argon2id, and why rehash on login?

**Answer:** Password hashes need to be slow. If the database leaks, attackers try billions of guesses offline, and a
fast hash like SHA-256 lets them do that on graphics cards. argon2id is deliberately slow and memory-hard, which makes
graphics cards much less useful, and it's the current OWASP recommendation. Each hash has a random salt stored inside
it. Rehashing on login is about the future: if I increase the cost settings, old hashes are still weaker. The only
moment I have the plain password is a successful login, so I check `check_needs_rehash` then and save a new hash.
