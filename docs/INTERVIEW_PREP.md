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

### 9. How did you optimise the site's images?

**Answer:** In two stages. At build time, a Node script uses sharp to convert the original 3 MB JPEGs to WebP at
quality 80, capped at 2400px wide for the hero and 1200px for everything else. It skips files that haven't changed
and prints sizes before and after. The seven photos went from 23 MB to 1.2 MB. At request time, `next/image`
generates several widths and the `sizes` attribute lets the browser pick the smallest one that's still sharp; I
checked in the network panel that a phone downloads about 245 KB of photos for the homepage, compared with 256px
tiles on desktop. Images below the fold load lazily, and only the hero is preloaded because it's the LCP element.

### 10. What does the `sizes` attribute do, and what happens if you get it wrong?

**Answer:** `next/image` produces a `srcset`, a list of the same image at different widths. `sizes` tells the
browser how wide the image will actually be on screen at each breakpoint, before the CSS has loaded, so it can choose
from the `srcset`. If you leave it out on a `fill` image, the browser assumes the image is as wide as the screen and
a phone downloads a full-width version for a small thumbnail. If you make it too small, images look blurry on
high-density screens. I matched each `sizes` value to the layout, like "50vw on phones, a third of the screen on
tablets, 200px on large desktops" for the category tiles.

### 11. Why aren't the original photos committed to git?

**Answer:** Git stores every version of every file forever. The originals are about 3 MB each and are never served
to visitors, so committing them would make the repository permanently bigger and every clone slower, and replacing a
photo would add another 3 MB to history rather than replacing it. I commit only the optimised WebP files, which the
site actually uses, and keep the originals out with `.gitignore`. The trade-off is that originals need their own
backup, since WebP can't be turned back into a full-quality original. A larger team might use Git LFS or object
storage for source assets.

### 12. How do product photos get from a folder on your laptop into the API?

**Answer:** I name each photo `{product-slug}-{color-slug}` or `{product-slug}-lifestyle` and run `npm run images`.
A sharp script converts it to a 4:5 WebP in `public/images/products/` and rewrites a manifest,
`backend/seed/image-manifest.json`, that lists every optimised file. Both are committed. Then `flask images sync`
reads the manifest, works out which product and colour each name belongs to from the database, and inserts or
updates `product_images` rows with generated alt text. The products API returns those rows, and the frontend renders
them with `next/image`. The manifest exists because the backend runs on Render and can't see the frontend's files, so
it needs a small committed list to learn which photos exist.

### 13. Your sync command runs on every deploy. How do you make that safe?

**Answer:** It's idempotent: running it again gives the same result. Each file's URL is unique in the table, so the
command looks up the existing row by URL and inserts, updates or skips it. A second run reports
`0 added, 0 updated, 34 unchanged`. It only touches `product_images`, and only rows whose URL is under
`/images/products/`, so orders, users and hand-added photos are never changed. It runs in one transaction, so a crash
can't leave half the rows updated. Rows for files that disappeared are deleted, so a rename can't leave a broken
image. A test proves orders and users are untouched, and `flask images check` gives a dry run.

### 14. Product photos come in different shapes. Why pad them instead of cropping?

**Answer:** Every card in the grid must be the same 4:5 shape. Cropping a square product photo to 4:5 cuts the sides,
which on a shirt are the sleeves, so the photo no longer shows the whole product. Padding keeps every pixel: the
script adds strips to the short sides, filled with the colour sampled from that edge, and on a plain studio
background you can't see the join. Lifestyle photos are different: they show a scene, so a centre crop is fine
there. A bug taught me to verify this by measuring: sharp's `.stats()` ignored my `.extract()`, so the first version
padded with the average colour of the whole photo, which made a visible grey band.

### 15. How is your homepage merchandised, and why not hard-code the featured products?

**Answer:** With tags. Products have a `tags` array column (`new`, `bestseller`, `autumn-edit`), and each homepage
section asks the API for a tag, like `GET /api/products?tag=new`. An admin edits tags in the product form, and the
homepage changes on the next request with no deploy. Hard-coded ids break silently when a product is deactivated,
and every change needs a developer. I used a Postgres array with a GIN index instead of a separate tags table
because tags are short labels with no data of their own. The query is `tags @> '{new}'`, which the GIN index can
answer. The same tag powers the "Shop the edit" link, `/shop?tag=autumn-edit`.

### 16. How did you add animation without hurting performance or accessibility?

**Answer:** I animate only `opacity` and `transform`, which the browser can animate without re-doing layout, so
layout shift stayed at 0. The hero text uses plain CSS, and the hero image isn't animated because it's the LCP
element. Scroll reveals use Motion with `LazyMotion` and the small `m` components to load only the features I need,
about 33 KB gzipped. I measured with and without it, and the Lighthouse score didn't change beyond noise. For
reduced motion, `MotionConfig reducedMotion="user"` turns off movement, CSS media queries swap slides for fades,
and a CSS rule removes the starting offset so sections don't jump. I verified that in a test browser by sampling
the element's transform.

### 17. Your newsletter endpoint returns the same message for new and existing emails. Why?

**Answer:** If "already subscribed" had a different response, anyone could type in an email and learn whether that
person is on our list. That's an enumeration leak, the same reason order tracking returns one identical 404. The
endpoint also lets the database enforce uniqueness with `INSERT … ON CONFLICT (email) DO NOTHING` instead of
"check, then insert", which two simultaneous requests could both pass. It accepts JSON only, which also blocks
cross-site HTML form posts, and it's rate limited per IP.

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

---

## Phase 4 — Payments with Stripe

### 1. Walk me through your checkout flow.

**Answer:** The browser sends variant ids, quantities, the address and the shipping method. Flask re-prices
everything from the database with the same function the cart uses, creates the order as `pending_payment` with
snapshots of each item, and creates a Stripe Checkout Session with the line items, the shipping amount, our order id
in the metadata, a 30-minute expiry and an idempotency key. The browser is redirected to Stripe's hosted page, so
card details never touch our servers. When payment succeeds, Stripe sends a signed webhook. That is what marks the
order paid and decrements stock, inside a transaction with row locks. The success page polls until it sees the
order is processing, then shows the confirmation.

### 2. Why fulfil orders from the webhook and not from the success page redirect?

**Answer:** The redirect isn't reliable or trustworthy. The shopper can close the tab, lose their connection, or
never reach the success URL, and anyone can type that URL into a browser. The webhook is server-to-server, signed
with a secret, and Stripe retries it for days until we return a 2xx. So the webhook is the source of truth, and the
success page only *reads* the order status, polling for a few seconds until the webhook has been processed.

### 3. How do you verify that a webhook really came from Stripe?

**Answer:** Stripe signs each webhook: it computes an HMAC-SHA256 of the timestamp plus the raw request body, using
a webhook secret that only Stripe and we know, and sends it in the `Stripe-Signature` header. We recompute it with
`stripe.Webhook.construct_event`. A forged or modified body fails the check, and we return 400. The timestamp is also
checked against a 5-minute tolerance, which stops replay attacks with old genuine events. One detail matters: we
verify the *raw* bytes from `request.get_data()`, because parsing and re-serialising the JSON would change the bytes
and break the signature.

### 4. Webhooks can arrive more than once. How is your handler idempotent?

**Answer:** Two layers. First, a `stripe_events` table with the Stripe event id as the primary key. I insert it in
the same transaction as the fulfilment: if the event was already processed, the row exists and we stop; if the
earlier attempt crashed, its insert rolled back, so the retry runs normally. Second, I lock the order row with
`SELECT ... FOR UPDATE` and only fulfil if it's still `pending_payment`, which covers two *different* events for the
same order. In the other direction, my calls *to* Stripe use idempotency keys like `checkout-order-42`, so a
network retry can't create two sessions or two refunds.

### 5. Explain the race condition when two people buy the last item, and how you prevented it.

**Answer:** Without locking, two webhooks can run at the same moment. Both read `stock = 1`, both compute zero, and
both write zero. Both orders are fulfilled, one item is sold twice, and the `CHECK stock >= 0` constraint doesn't
help because zero is valid. That's a lost update. I lock the variant rows with `SELECT ... FOR UPDATE`, so the second
transaction waits until the first commits and then reads `stock = 0`. I always lock in id order to avoid deadlocks.
I have a test that sends both webhooks from two threads at once; with the lock one order is fulfilled and the other
cancelled and refunded. I also ran it with the lock removed, and it failed with both fulfilled.

### 6. Stock is only taken after payment. What happens if it sells out while someone is paying?

**Answer:** That's the trade-off of not reserving stock. Abandoned checkouts never hold stock, but very occasionally
two people pay for the last item. The webhook detects it under the row lock, cancels the order with a clear note, and
refunds automatically through Stripe with an idempotency key. The refund call happens after the transaction commits,
because holding row locks during a network call would block other checkouts for those products. If the refund call
fails, it's logged and the order is marked as needing a manual refund. For a limited-edition drop I'd switch to
reserving stock at checkout and releasing it when the session expires.

### 7. How do unpaid orders expire?

**Answer:** Three layers. The Stripe session has `expires_at` set to 30 minutes, so after that nobody can pay it.
Stripe then sends `checkout.session.expired`, and the handler cancels the order if it's still pending. Because
webhooks can be missed, a CLI command, `flask orders expire-unpaid`, cancels pending orders older than an hour. It
uses `FOR UPDATE SKIP LOCKED` so it never fights with a webhook processing the same order, and it refuses a cut-off
shorter than the session lifetime. There's also an edge case: a payment arriving for an order we'd already
cancelled triggers an automatic refund.

### 8. What did end-to-end testing find that unit tests didn't?

**Answer:** My unit tests replace Stripe with a fake that accepts any parameters. When I ran the whole flow in a
browser against stripe-mock, Stripe's official mock server that validates requests against the current API schema,
checkout failed: in this Stripe API version, `payment_method_types` had been replaced by
`allowed_payment_method_types`. Every real checkout would have failed. I fixed it and added a test that checks every
parameter we send exists in the installed Stripe library's type definitions. The lesson: mocks only test what you
assume, so you need at least one test against something that knows the real contract.

### 9. Why did you build your own sandbox payment provider?

**Answer:** Stripe doesn't support accounts in Pakistan, so I couldn't get keys, and checkout would just stop. I
didn't want to fake it by skipping payment, because the interesting engineering is in the webhook: signature
verification, idempotency and locking stock. So I built a sandbox provider that behaves like Stripe: a hosted payment
page clearly labelled "no real money", Stripe's test card numbers (4242 succeeds, 4000…0002 is declined), and a
webhook event in Stripe's shape, signed with HMAC-SHA256 plus a timestamp. The order is still only fulfilled by a
verified webhook, through exactly the same handler. It's the default, so the live demo works for anyone, and Stripe
is one environment variable away.

### 10. What is the adapter pattern, and how did you use it?

**Answer:** An adapter translates between the interface your code wants and the interface something else provides,
like a travel plug adapter. I defined a `PaymentProvider` abstract base class with four methods:
`create_checkout_session`, `verify_webhook`, `parse_event` and `refund_payment`. Checkout builds a provider-neutral
`CheckoutRequest`, with nothing Stripe-specific in it. `StripeProvider` translates that into Stripe's API parameters
and uses Stripe's library to verify webhooks; `SandboxProvider` creates its own session and verifies its own
signatures. Both produce events in the same shape, so the webhook handler, the idempotency table and the stock logic
didn't change at all. To prove the Stripe behaviour was unchanged, all 35 existing Stripe tests passed after the
move. Adding PayPal or JazzCash would mean writing one new class.

### 11. Explain how HMAC webhook signing works.

**Answer:** The sender and receiver share a secret. To sign, the sender takes the current Unix timestamp, joins it to
the exact raw body with a dot, and computes HMAC-SHA256 of that with the secret. It sends `t=<timestamp>,v1=<hex
digest>` in a header. The receiver parses the header, rejects timestamps older than five minutes to stop replay
attacks, recomputes the HMAC over the raw bytes, and compares with `hmac.compare_digest`. Without the secret nobody
can produce a valid signature, and changing one byte of the body, or the timestamp, which is inside the HMAC, breaks
it. Two subtle points: verify the raw bytes before parsing the JSON, because re-serialising can change them; and use
a constant-time comparison, because a normal `==` returns faster the earlier the strings differ, which leaks
information an attacker can measure.

### 12. Your sandbox "sends itself" a webhook. Why not just make an HTTP request to your own URL?

**Answer:** Because it can deadlock. In production, gunicorn might run one synchronous worker. That worker is busy
handling the payment request; if it makes an HTTP request to itself and waits for the answer, there's no free worker
to answer, so it waits forever. I also didn't want to call the handler function directly, because that would skip
signature verification, the part I most wanted to exercise. So I use Flask's `test_client()`: it builds a real
request and runs it in-process through the full stack — routing, error handlers, signature and timestamp checks, and
the webhook handler — without a network hop. With a real provider, the webhook would come from Stripe's servers
instead, and nothing else changes.


### 13. You added cash on delivery. Why is stock reserved immediately for COD, but only after payment for card?

**Answer:** For card orders, most started checkouts are never paid, so reserving stock at checkout would hide items
from real buyers for up to 30 minutes per abandoned checkout. I take stock in the webhook, once the money is
confirmed, and handle the rare "sold out while paying" case with an automatic refund. A COD order has no later payment
moment before shipping: I promise to ship as soon as it's placed. So I take the stock right away, in the same
transaction that creates the order, with the same row locks the webhook uses. If anything sold out, nothing is saved.

### 14. What's the fraud risk of cash on delivery, and how did you limit it?

**Answer:** Placing a COD order costs nothing, so someone could create fake orders that hold stock (real shoppers then
see "sold out") and waste courier trips. I rate limit COD orders to 3 an hour and 10 a day per IP, plus 3 a day per
phone number, because attackers with many IPs usually reuse a few numbers. Refused attempts count too, so probing isn't
free. A phone number is required, COD is for US addresses only, and admins can cancel, which puts the stock back. A
real shop would add SMS verification, a maximum COD amount and blocking numbers with refused deliveries.

### 15. How did you change payment data and policy text on a database you can't reset?

**Answer:** Two ways. For the new `payment_status` column, the migration set each existing order's status from its
history: never paid stays `unpaid`, returned or cancelled-after-payment becomes `refunded`, everything else `paid`. A
test downgrades the database, inserts one old order of each kind, upgrades it and checks the result. For the policy
text, each policy in the seed file has a `version`, and `flask policies sync` only applies a higher version. It runs on
every deploy, it's idempotent, and an admin's edit survives until I deliberately ship a new version: like migrations,
but for content.

---

## Phase 5 — Order tracking and returns

### 1. How does your order tracking avoid leaking information?

**Answer:** Guests track with order number plus email, and I look them up in one query: `WHERE order_number = ? AND
email = ?`. If I fetched by number and then compared emails, there would be two failure paths, "no such order" and
"wrong email", which could differ in message, status code, or timing. With one query there's one path, and every
failure returns the same 404 with the same message. The response also leaves out the street address and payment
details, because knowing an order number and an email isn't strong proof of identity. And it's a POST, so the email
never ends up in URLs, logs or browser history.

### 2. How did you rate limit order lookups, and why only count failures?

**Answer:** With Flask-Limiter's shared limits: tracking, return eligibility and creating a return share one budget,
so switching endpoints doesn't give extra attempts. There are two keys: per IP, 10 a minute and 60 an hour, and per
order number, 20 an hour, which stops many IPs guessing emails for one known order. I set `deduct_when` so only
404 responses count. The threat is guessing, and every wrong guess is a miss; a successful lookup tells the caller
nothing they didn't already know. I found this was needed in browser testing: a real customer tracking an order,
checking eligibility and submitting a return was hitting the limit.

### 3. How did you turn the returns policy into code?

**Answer:** I took each sentence of the policy and made it a small, named function that returns either nothing or a
refusal with a code and a human message: delivered only, not cancelled, not already returned, within 30 days of
delivery, no final-sale items, quantities minus open returns, the condition confirmation, free US labels versus
international customers paying, and exchanges only for an in-stock variant of the same product. The current time is
a parameter, not read inside the rules, so tests can check any moment. There's one test per rule, plus boundary
tests: day 30 is allowed, 30 days plus one minute isn't. The codes matter for Phase 8: the AI agent will call the
same functions and use the codes to decide what to tell the customer.

### 4. Why does final sale use the order item, not the product?

**Answer:** Because the rule should apply to what was true when the customer bought it. Order items snapshot the
product name, price and final-sale flag at purchase time. If we later stop marking the socks as final sale, someone
who bought them under the final-sale terms shouldn't suddenly be able to return them, and the other way round. I
have a test that changes the product today and checks the old order still refuses the socks.

### 5. The frontend already disables non-returnable items. Why check again on the server?

**Answer:** Because the frontend is a convenience, not a security boundary. Anyone can send a request directly with
curl or DevTools. `create_return` re-runs every rule against the exact request and returns a 422 with the refusal
code if something isn't allowed. It also locks the order row with `SELECT ... FOR UPDATE` while it checks quantities
and inserts the request, so a double click or two tabs can't both return the last unit of an item. That's the same
lesson as decrementing stock in Phase 4.

### 6. What is boundary testing? Give an example from your project.

**Answer:** Testing exactly at the edge of a rule, because off-by-one mistakes hide there. The return window is
"within 30 days of delivery". I test exactly 30 days after delivery, which should be allowed, and 30 days plus one
minute, which shouldn't. That decides whether the comparison is `>` or `>=`. A related bug I found: the "days left"
counter used `timedelta.days`, which rounds down, so with 7 days and 23 hours left it said 7 days. I changed it to
round up and added a test.

### 7. Describe a bug that only appeared in production.

**Answer:** After signing up, users were sent back to the login page. The API returned 201 and the cookies were set
correctly. The cause was Next.js prefetching: in production it prefetches visible links, and the header's "Your
account" link was prefetched while the visitor was logged out, so the client router cached "redirect to /login".
After signup, the client-side navigation reused that cached redirect. It never appeared in development because `next
dev` doesn't prefetch, which is also why my earlier tests passed. I fixed it by doing a full page load after login,
signup and logout. That clears every client-side cache, which is also good for privacy on logout. The lesson: run
end-to-end tests against a production build.

### 8. How do logged-in customers start a return without typing their email?

**Answer:** The lookup takes either an email or the logged-in user. With an email, it matches number plus email;
without one, it matches number plus `user_id` from the verified session cookie. So a customer coming from their
account's order page only needs the order number, and the request carries the CSRF header like every other write.
We never match a logged-in user to guest orders by email, because emails aren't verified; someone could sign up with
your address. If an order isn't linked to the account, they enter the email like a guest.

---

## Phase 6 — Admin dashboard

### 1. What's the difference between authentication and authorization, and between 401 and 403?

**Answer:** Authentication is proving who you are; here, a valid JWT cookie. Authorization is deciding what you're
allowed to do; here, whether your role is admin. A logged-in customer is authenticated but not authorized for admin
routes. The status codes follow that: 401 means "not authenticated, log in", and 403 means "authenticated, but
forbidden". My admin API returns 401 with no cookie and 403 for a customer, and both have tests.

### 2. How do you make sure every admin route is protected?

**Answer:** Two ways. In the code, the check isn't on the routes at all: it's a `before_request` hook on the admin
blueprint, so it runs before every route in it, including any added later. It verifies the JWT, which also enforces
CSRF on writes, then checks the role. In the tests, I don't list routes by hand. I loop over Flask's URL map, find
everything under `/api/admin`, and check that anonymous gets 401, a customer gets 403 even with a valid CSRF header,
and an admin gets through. Another test asserts the loop found at least 15 routes, so a broken discovery can't pass
silently. I also disabled the hook once to confirm the tests fail.

### 3. If you remove someone's admin role, when does it take effect?

**Answer:** On their next request. The JWT only contains the user id. On every request, Flask-JWT-Extended's user
loader fetches the user from the database, and the admin check reads the role from that fresh row. If I'd put the
role inside the token, a demoted admin would keep admin access until the token expired, up to 7 days. The cost is
one primary-key lookup per request, which is negligible. There's a test that demotes an admin and checks the same
cookie gets 403 straight away.

### 4. Why do admins adjust stock with +/- changes instead of typing the new number?

**Answer:** To avoid a lost update. The admin's page shows 25, a customer buys one so it's really 24, then the admin
types 35 after receiving 10. Saving an absolute 35 would erase the sale. Instead the API takes a change, `+10`, and
applies it in one SQL statement: `UPDATE ... SET stock = stock + 10 WHERE id = ? AND stock + 10 >= 0`. Postgres does
that atomically against the current value under a row lock, so the result is 34 and both changes count. The WHERE
clause also refuses anything that would go negative. There's a test with exactly this scenario.

### 5. Explain the order state machine and why you need one.

**Answer:** It's a table of allowed moves: processing can go to shipped, partially shipped or cancelled; shipped can
go to out for delivery, delayed or delivered; delivered, cancelled and returned are final. The server refuses
anything else with a 409 that lists the allowed moves, and the detail endpoint exposes `allowed_next_statuses` so the
UI only offers valid choices. Each status has its own rules: shipping needs a carrier and tracking number, a delay
needs a note for the customer, and delivered starts the return window. Without it, a misclick could produce
impossible histories like delivered then processing, which would confuse customers, the tracking page and the AI
agent.

### 6. What is an audit trail, and how did you build one?

**Answer:** A record of who changed what and when, which isn't edited afterwards. Every order and return change
inserts a row into `order_events` with the status, a note, a timestamp and `created_by`: system for webhooks, admin
for staff, and agent for the AI assistant in Phase 8. Rows are only ever added. The same table drives the customer's
tracking timeline, the admin's history view and, later, the agent's view of what happened. A gap I'd close next is
product and policy edits, which aren't logged yet; I'd add an admin actions table with the user id and before/after
values.

### 7. How are the dashboard statistics computed?

**Answer:** With SQL aggregates, so Postgres does the work and returns a few numbers instead of every order:
`SUM(total_cents)` and `COUNT(*)` filtered to paid statuses and the last 7 or 30 days, a `GROUP BY` on
`date_trunc('day', created_at)` for the daily chart, a `GROUP BY status` for the breakdown, and a join with a
`stock <= 5` filter for low stock. Python only fills in days with no sales so the chart has 30 bars. The test
recomputes the same totals a different way, in Python from the orders, and compares.

### 8. Your admin UI hides the admin area from customers with a 404. Isn't that security through obscurity?

**Answer:** It would be if it were the only protection, but it isn't. The real boundary is the Flask check on every
admin API call: even if a customer found the pages, every request returns 403. The 404 is about not advertising the
area and giving a clean experience. The page gate, the proxy redirect and the 404 are courtesies; the server is the
lock. That's the same rule as in Phase 5, where the returns page disables final-sale items but the server still
refuses them.

### 9. Your proxy reads the user's role from the JWT without verifying it. Isn't that insecure?

**Answer:** It would be if the role decided access, but it only decides routing. At login Flask adds a `role` claim
to the token as a hint. The Next.js proxy reads it, without the secret, to redirect an admin from `/account` to
`/admin` before the customer page renders, and the header uses it to show an Admin badge. Every decision about
data is made by Flask, which ignores the claim and reads the role from the database on each request. If someone
forges "admin", they're redirected to `/admin`, the page asks Flask, and they get a 404, with 403 from every admin
API. I have a test where even a validly signed token claiming admin for a customer gets 403. The rule: the UI can
hide and redirect, but only the backend enforces.

---

## Phase 7 — Deployment

### 1. Walk me through how your app is deployed.

**Answer:** Three managed services on free plans, all in US East. The Next.js site is on Vercel, the Flask API on
Render, and Postgres on Neon. The browser only talks to Vercel, which forwards `/api` to Render, so cookies are
first-party and there's no CORS. Render's setup is code in `render.yaml`. On each deploy it installs pinned packages
and runs `start.sh`, which applies Alembic migrations, syncs product photos, then `exec`s gunicorn. Pushing to
`main` redeploys both apps. An hourly GitHub Actions job cancels unpaid orders, because Render's free plan has no
cron jobs.

### 2. Why gunicorn, and why one worker with four threads?

**Answer:** `flask run` is a development server. Gunicorn is a production WSGI server that manages workers, kills
stuck requests after a timeout, and shuts down gracefully on deploys. Our requests mostly wait on the database, and
threads share that waiting well. A single process also keeps the in-memory rate-limit counters correct: with three
workers, each would count separately and every limit would triple. The production config refuses `memory://` rate
limits with more than one worker. To scale up I'd move the counters to Redis and raise the worker count.

### 3. How do you connect to a serverless database like Neon safely and reliably?

**Answer:** Safely: the connection string must have `sslmode=require`, and the production config refuses to start
without it. Reliably: Neon's compute sleeps after five idle minutes and drops connections, so SQLAlchemy uses
`pool_pre_ping` and recycles connections after five minutes. Otherwise the first request after a quiet period fails.
I use Neon's pooled endpoint, which is PgBouncer in transaction mode. Consecutive transactions can land on different
server connections there, so I turn off psycopg's automatic prepared statements, which live on a single connection.

### 4. What's the difference between a liveness and a readiness check, and why do you have both?

**Answer:** Liveness asks "is the process running?" and readiness asks "can it do its job, for example reach the
database?". Render's health check uses liveness, `/api/health/live`, with no query. If it ran `SELECT 1` every few
seconds, Neon's compute could never sleep, and we'd burn the free compute hours. A database blip could also make
Render restart a perfectly healthy process. `/api/health` still checks the database for people and monitoring, and
the start script runs migrations first, so a deploy can't succeed without a working database.

### 5. How do you stop a misconfigured production deploy?

**Answer:** It fails fast. `ProductionConfig` checks the environment at startup and refuses to run if a secret is
shorter than 32 characters or still a placeholder, if `FRONTEND_URL` isn't https, if a remote database URL lacks
TLS, if Stripe is missing a key, or if in-memory rate limits meet several workers. It lists every problem at once,
so one failed deploy shows everything to fix. Because the start script runs `set -e`, a failing migration also stops
the new version from starting. A loud, clear failure on deploy is much better than a site quietly running insecurely.

### 6. Which security headers do you send, and why does your CSP allow inline scripts?

**Answer:** The API returns only JSON, so it gets the strictest policy: `default-src 'none'`, no framing, `nosniff`,
no referrer, and HSTS. The website sends HSTS, `nosniff`, `X-Frame-Options`, a permissions policy, and a CSP that
limits scripts, fonts and API calls to our own origin and forbids framing and plugins. Next.js needs small inline
scripts. The strict fix is a nonce per response, but that forces every page to render per request and we'd lose the
prerendered static shell. So I allow inline scripts and keep everything else locked down. React's escaping is the
main defence against injected HTML anyway.

### 7. How does your rate limiter know the real client IP behind two proxies?

**Answer:** Each proxy appends to `X-Forwarded-For`, so the chain is "client, Vercel" and Render's load balancer is
the direct peer. `ProxyFix(x_for=2)` takes the second value from the right, the address our first trusted proxy
saw. Anything further left could be typed by the client, so we never trust it. If the count is too low, attackers
can fake their IP. If it's too high, everyone falls back to the load balancer's IP and shares one rate limit. I log
the chain in gunicorn's access log and checked it on the live site instead of assuming.

## Phase 8A — Email notifications (the outbox)

### 1. Why not just call the email API inside the request that changes the order?

**Answer:** Because it's a **dual write**: the database and the email provider are two systems, and no single
transaction covers both. If I send first and the commit then fails, the customer reads "your order shipped" about a
change that never happened. If I commit first and then crash or Resend is down, the email is lost and nobody knows.
It also makes the admin's click wait on a third-party API. So the request only writes an outbox row, inside the same
transaction as the order change, and sending happens after the commit (`backend/app/mail/outbox.py`).

### 2. Explain the transactional outbox pattern.

**Answer:** You turn "send an email" into "insert a row" in the same transaction as the business change. The commit
makes both real together, or neither. A separate step reads pending rows and delivers them, and marks each one sent.
If delivery fails, the row is still there, so it's retried. In Kora, a SQLAlchemy `after_commit` hook sends new rows
in a background thread within seconds, an `after_rollback` hook forgets them, and a GitHub Actions job calls
`POST /api/email/outbox/process` every 5 minutes as the safety net. The same pattern is used to publish events to
Kafka or a queue reliably. The queue publish is just as much a dual write as an email.

### 3. The outbox gives at-least-once delivery. How do you avoid sending duplicates?

**Answer:** Two layers of idempotency. First, every row has a unique `idempotency_key`, like
`order-confirmation:42` or `order-status:42:<event id>`, and we insert with `ON CONFLICT DO NOTHING`. So if Stripe
retries a webhook or an admin double-clicks, the database refuses the second row, even when the two requests race.
Second, we pass the same key to Resend in the `Idempotency-Key` header. The dangerous moment is a crash after Resend
accepted the email but before we saved "sent". The retry reuses the key and Resend doesn't deliver it again. Both
layers are tested.

### 4. How do retries work, and what stops two workers sending the same email?

**Answer:** A sender claims due rows in a short transaction: `SELECT … FOR UPDATE SKIP LOCKED`, sets them to
`sending` with a 2-minute **lease** (`locked_until`), and commits. Then it calls the provider with no database locks
held, because holding locks during a network call would block other work. On success the row is `sent`. A
temporary error (network, 429, 5xx) puts it back to `pending` with exponential backoff: 1, 5, 15, 60 and 240
minutes. A permanent 4xx, or the 6th failure, makes it `failed`. If a sender dies mid-send, its lease expires and
the next run takes the row over. `SKIP LOCKED` makes concurrent senders take different rows, and an advisory lock
keeps the daily-cap count exact.

### 5. A public demo store can be used to spam strangers. What did you do about it?

**Answer:** Anyone can type any email at checkout or sign-up, so I use different rules for accounts and guests.
**Accounts** confirm their address once, with a signed link (itsdangerous, salted, 7-day expiry). Until then they
can shop, but their order emails are recorded as suppressed. **Guests** get their receipt directly, and abuse is
stopped by layers instead: Cloudflare Turnstile on guest checkout, so bots can't place orders; at most two
guest-order confirmations per address per day; a global daily cap under Resend's free tier; and reserved domains
like `example.com` are never emailed. Every suppressed email is still recorded with a reason, so support can see
what wasn't sent and why.

### 6. What are SPF, DKIM and DMARC, and why do they matter for your project?

**Answer:** They let receiving mail servers check that an email claiming to be from our domain really is. **SPF** is a
DNS record listing the servers allowed to send for the domain. **DKIM** signs each email with a private key, with
the public key published in DNS, which proves the email came from us and wasn't changed. **DMARC** tells receivers
what to do when those checks fail, and where to send reports. Without them, emails go to spam or get rejected,
and Gmail and Yahoo now require them for bulk senders. I send from a subdomain, `kora.abdullahrasheed.tech`, so the
demo store's reputation can't hurt my main domain.

### 7. Why Resend over HTTP rather than SMTP, and how do you test email locally?

**Answer:** Render's free plan blocks outgoing SMTP ports to fight spam, so production uses Resend's HTTPS API through
`httpx`. That also gives us idempotency keys and clear status codes for deciding what to retry. All providers share
one tiny interface, `send(email) -> message_id`, the same adapter pattern as our payment providers.
`EMAIL_PROVIDER` picks `resend`, `mailpit` or `log`. Locally, Mailpit runs in Docker and catches every email over
SMTP, so I see the real HTML, headers and Reply-To at localhost:8025, and nothing can reach a real person. Tests use
a recording fake, and `httpx.MockTransport` for the Resend request shape and error classes.

### 8. Your retry job runs every 5 minutes. Doesn't that keep your serverless database awake?

**Answer:** It would. Neon's free compute sleeps after about 5 minutes idle, and a query every 5 minutes would keep
it awake all month and use up the free compute hours. So the process keeps a small in-memory flag, "might anything
be waiting?". It's set after any commit that wrote an outbox row, cleared by a run that finds nothing waiting, and
starts as true after every restart, so a crash is still covered. When it's false, the endpoint answers without
touching the database. That's safe because we run one process. With many instances, I'd move the flag into the
database or use a real scheduler.

### 9. Why don't guests have to confirm their email, when account holders do?

**Answer:** It's a trade-off between friction and abuse. A guest typed their address seconds ago to get a receipt.
My first version sent them a "confirm your email" link first, and that loses real customers' confirmations, because
many won't click, especially on mobile. An account is different: it's cheap to create with a script and it keeps
receiving email for its whole life, so one click at sign-up is worth it. For guests I moved the protection to the
places an attacker has to pass: Turnstile before the order exists, the cash-on-delivery rate limits, and a cap of
two guest confirmations per address per day. The worst case for a stranger is two emails a day, and only after
the attacker solved a CAPTCHA.

### 10. How does Turnstile work, and why verify the token on the server?

**Answer:** The widget runs in the shopper's browser, mostly invisibly, and returns a one-time token. The page sends
that token with the order. The **server** posts it to Cloudflare's `siteverify` API with our secret key and the
client's IP, and only creates the order if Cloudflare says it's valid and was made for the `checkout` action. A
check only in the browser would be pointless: a bot just calls our API directly and skips the widget. A token
works once and expires after 5 minutes, so it can't be replayed, which is why the widget resets after any failed
attempt. Logged-in customers skip it: an account is already a barrier.

### 11. If Cloudflare is down, do guest orders still work?

**Answer:** No. It fails closed: the API answers 503 "we couldn't run the security check, try again". Failing open
would keep the shop working, but then anyone who can make the check fail, for example by blocking the call, would
switch the protection off. The impact is small: it only affects guests, logged-in customers can still order, and
Cloudflare outages are rare and short. It's a conscious choice, and I can name the cost.

### 12. Two guest orders for the same address arrive at the same moment. How do you keep the "2 a day" cap exact?

**Answer:** The cap is checked when the confirmation is written, inside the order's transaction. Just before
counting, I take a Postgres advisory lock on a hash of the address: `pg_advisory_xact_lock(hashtext(...))`. A second
transaction for the same address waits at that line until the first commits, then counts again and sees the new
row. Without the lock, both could count "1 so far" and both send. The lock is per address, so different customers
never wait for each other, and it's released automatically at commit or rollback.

### 13. A user signs up with a typo in their email. What happens?

**Answer:** They land on a "check your email" page, already logged in, showing the address the link went to. There's
a resend button with a countdown, which matches the server's rate limit of one a minute. If they're limited anyway,
the API's `Retry-After` header drives the countdown. "Wrong email? Change it" asks for the new address **and the
password**, so a stolen session cookie alone can't redirect the account to an attacker's mailbox. It only works
while the address is unconfirmed. Changing a confirmed address properly means confirming the new one before
switching, which is a separate feature.
