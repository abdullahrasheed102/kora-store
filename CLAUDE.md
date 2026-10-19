# Kora Outfitters — Project Guide for Claude Code

Kora Outfitters is a fictional clothing store built as a portfolio demo by Abdullah Rasheed (AI Engineer).
It has to look and behave like a real, professional e-commerce store, because it is the showcase for an
AI customer support agent that will be added later. The full spec and build phases are in `docs/PLAN.md`.
Work one phase at a time and don't start the next phase until the current one passes its checks.

## How we work (read this first)
This is Abdullah's portfolio project for entry-level AI engineering jobs. **Claude writes all the code**
(frontend, backend and the AI agent). Abdullah's goal is to **understand and explain every part of it in
interviews**, so teaching is part of every task, not an extra.

- **Before coding a task**, explain in plain language: what you're building, why it's needed, how it fits the
  architecture, and the alternatives for any real design choice (and why we picked this one).
- **While coding**, write clean, readable code. Add short comments that explain the "why" on anything non-obvious.
  Don't comment the obvious.
- **After each phase** (required before the phase counts as done):
  1. Run the tests and checks (`pytest`, `npm run lint && npm run build`) and show the results.
  2. Write the phase guide in `docs/guide/` (see Documentation below).
  3. Update `docs/ARCHITECTURE.md`.
  4. Add 5–8 interview questions with model answers to `docs/INTERVIEW_PREP.md`.
  5. Add new terms to `docs/GLOSSARY.md`.
  6. Tell Abdullah how to try it himself, and offer to quiz him.
- **When Abdullah asks a question**, answer at beginner level first, then go one level deeper. Use examples
  from our actual files (with `path:line` references).
- Abdullah develops on **Ubuntu Linux**. Give shell commands for bash on Ubuntu.

## Documentation
Write all docs in simple English with short sentences. Define each piece of jargon the first time it appears.
Abdullah's first language is Urdu, so prefer plain words over idioms.

- `docs/ARCHITECTURE.md` — the whole system on one page: a Mermaid diagram of all the parts (browser, Next.js,
  Flask, Postgres, Stripe, the agent) and how a request flows through them. Mark what is built and what is planned.
  Update it after every phase.
- `docs/guide/NN-topic.md` — one guide per phase (`00-project-setup.md`, `01-database.md`, …). Each guide has
  these sections:
  - **What we built**
  - **Key concepts**
  - **How it works here** — a file walkthrough with short code excerpts
  - **Request flow** — a Mermaid sequence diagram
  - **Design decisions and alternatives**
  - **What could go wrong**
  - **Try it yourself**
  - **Explain it in 60 seconds** — a short script Abdullah can say in an interview
- `docs/INTERVIEW_PREP.md` — interview questions with model answers, grouped by phase.
- `docs/GLOSSARY.md` — every technical term we use, in alphabetical order, each with a one- or two-sentence
  plain-English definition and where it appears in the project.

## Stack
- `frontend/` — Next.js (latest, App Router, TypeScript) + Tailwind CSS. Deployed on **Vercel**.
- `backend/` — Flask (Python 3.12) with SQLAlchemy 2.x, Flask-Migrate (Alembic), Pydantic for validation, gunicorn. Deployed on **Render**.
- Database — **Neon Postgres**. Local development may use a local Postgres (docker compose) or a Neon dev branch; never SQLite, so behaviour matches production.
- Payments — **Stripe Checkout in test mode** only.
- `agent/` (phase 8) — Python multi-agent customer support built with LangGraph, using Groq and Gemini models. It calls the backend's `/api/agent/*` endpoints as tools and is exposed to the site through a chat endpoint. Includes an evaluation set (`agent/evals/`) of test conversations with expected outcomes.

## Architecture rules
- The browser only ever calls the frontend's own origin. `frontend/next.config` rewrites `/api/:path*` to the Flask backend (`BACKEND_URL`). This keeps auth cookies first-party and avoids CORS problems between vercel.app and onrender.com.
- All Flask routes live under `/api`. Use blueprints: `auth`, `products`, `cart` (validation/pricing only), `checkout`, `orders`, `admin`, `agent`, `health`.
- Auth: session token in an httpOnly, Secure, SameSite=Lax cookie (Flask-JWT-Extended with cookies, CSRF protection on). Passwords hashed with argon2 or bcrypt.
- Money is always stored and computed as integer cents. The backend recalculates every price and total; never trust prices sent by the client.
- Stock is decremented only when Stripe confirms payment (webhook), inside a transaction with row locks.
- Orders have a human-friendly `order_number` (`KO-1001`, `KO-1002`, …) in addition to the internal id.
- Every order status change writes a row to `order_events` (this becomes the tracking timeline and the agent's history).
- Store policies live in the `policies` table and are rendered on the site from there — one source of truth for the website and the future AI agent.
- The `/api/agent/*` routes are reserved for the AI support agent (phase 8). They are protected by an `X-Agent-Key` header, never by user cookies.

## Conventions
- Backend: app factory (`create_app`), config from environment variables only, `.env.example` kept up to date. Type hints everywhere. Errors return JSON `{ "error": { "code", "message" } }` with proper HTTP status codes.
- Frontend: server components by default; client components only where interactivity is needed. Cache Components is on: anything reading `params`/`searchParams` or doing an uncached fetch goes inside `<Suspense>`, so `npm run build` never needs the API. Read `frontend/node_modules/next/dist/docs/` before using a Next.js API (this version differs from older ones). Fetch data through a small typed API client in `frontend/lib/api.ts`. Cart state in a React context persisted to localStorage.
- Design: clean, warm, editorial look. Fonts Fraunces (headings) + Inter (body). Palette: ink `#1f1b16`, background `#f7f3ec`, card `#fffdf9`, accent `#b4532a`, sage `#dfe6d6`. Fully responsive and accessible (labels, focus states, alt text, keyboard navigation).
- Product images: no copyrighted brand imagery. Use `image_url` fields (royalty-free photos or generated placeholders); admins can change them.
- Site photos: originals go in `image-originals/site/` or `image-originals/products/` (git-ignored); `cd frontend && npm run images` writes WebP files to `frontend/public/images/`, which are committed. Use `next/image` with alt text and a `sizes` value matching the layout; only the homepage hero uses `preload`.
- Product photos: name originals `{product-slug}-{color-slug}` or `{product-slug}-lifestyle` (e.g. `linen-button-up-shirt-sky-blue.jpeg`). `npm run images` pads colour photos to 4:5 (never crops them), centre-crops lifestyle photos, and rewrites `backend/seed/image-manifest.json` (committed). Then `cd backend && flask images sync` (idempotent; never resets data) fills `product_images`. `flask images check` reports misnamed and missing photos without changing anything. Never rename a photo without asking.
- Homepage sections are chosen by product **tags** (`new`, `autumn-edit`, `bestseller`), never by product ids; the perks strip reads policy `summary` fields. The AI assistant button is switched by `NEXT_PUBLIC_ASSISTANT_ENABLED`.
- Animation: calm (200–500ms, `ease-calm`, no bounce), only `opacity`/`transform`, never on the LCP image. Use CSS where it's simple and `Reveal` (Motion, `m` components inside `LazyMotion`) for scroll reveals. Every animation must respect `prefers-reduced-motion` (fade or nothing).
- Tests: pytest for the backend (models, pricing, checkout webhook, auth, order lookup). Add tests with each phase. Run them before saying a phase is done.
- Never commit secrets. Stripe keys, database URLs and the agent key come from environment variables.

## Seed data
`backend/seed/` contains `products.json` (20 products, 217 variants), `orders.json` (12 demo orders) and `policies.json`.
Order dates are relative (`created_days_ago`, `delivered_days_ago`, `estimated_delivery_in_days`) — the seed script converts them to real dates at seed time so the demo never goes stale. Run `flask seed --reset` to rebuild demo data. Demo orders are guest orders (no user account) using the emails in the file.

## Commands (keep these working)
- Backend: `cd backend && flask db upgrade && flask seed --reset && flask run` · tests: `pytest` · after adding photos: `flask images sync`
- Frontend: `cd frontend && npm run dev` · checks: `npm test && npm run lint && npm run build`
- Production: Render runs `backend/start.sh` (migrations → image sync → gunicorn, settings in `render.yaml` and `backend/gunicorn.conf.py`); Vercel builds `frontend/`. Steps in `DEPLOY.md`. Never run `flask seed --reset` against Neon.
