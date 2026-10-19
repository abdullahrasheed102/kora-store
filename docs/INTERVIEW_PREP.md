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
