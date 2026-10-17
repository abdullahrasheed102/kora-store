# Kora Outfitters — Project Guide for Claude Code

Kora Outfitters is a fictional clothing store built as a portfolio demo by Abdullah Rasheed (AI Engineer).
It has to look and behave like a real, professional e-commerce store, because it is the showcase for an
AI customer support agent that will be added later. The full spec and build phases are in `docs/PLAN.md`.
Work one phase at a time and don't start the next phase until the current one passes its checks.

## How we work (read this first)
This is Abdullah's portfolio project for landing an AI / backend engineering job, so the goal is for him to
**learn and be able to explain every line of the backend and the AI agent**. The two halves are handled differently:

**`frontend/` — build mode.** Claude builds the frontend fully and independently, to a professional standard.
Abdullah reviews it but doesn't need to write it.

**`backend/` and `agent/` — mentor mode.** Abdullah writes the important code himself; Claude teaches, guides and reviews.
- Before each task, explain the concept in a few sentences (what it is, why we need it, how it fits the architecture), then propose a short plan.
- Claude may write boilerplate: config, app factory wiring, migrations generated from models, test fixtures, deployment files, and seed loaders.
- Abdullah writes the core logic: models, routes, validation, pricing and stock rules, auth, checkout and webhook handling, return eligibility, and every part of the agent (state, nodes, tools, prompts, routing). Mark these spots with `TODO(human)` and describe what to write, the inputs and outputs, and the trade-offs to weigh. Don't write the solution unless he asks for it.
- Write or outline the tests first where it helps, so he can check his own code by running `pytest`.
- When he says he's done, review his code like a senior engineer: correctness, security, edge cases, naming. Explain the why behind each suggestion and let him make the fix.
- If he's stuck, give hints in increasing order (a pointer, then pseudocode, then a partial snippet) before a full answer.
- At the end of each phase, give 3–5 interview-style questions about what he built, and add a short entry to `docs/LEARNING_LOG.md` (concepts covered, decisions made, and why).
- Recommended: run `/output-style learning` when working on backend or agent tasks, and switch back with `/output-style default` for frontend work.

## Stack
- `frontend/` — Next.js (latest, App Router, TypeScript) + Tailwind CSS. Deployed on **Vercel**.
- `backend/` — Flask (Python 3.12) with SQLAlchemy 2.x, Flask-Migrate (Alembic), Marshmallow or Pydantic for validation, gunicorn. Deployed on **Render**.
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
- Frontend: server components by default; client components only where interactivity is needed. Fetch data through a small typed API client in `frontend/lib/api.ts`. Cart state in a React context persisted to localStorage.
- Design: clean, warm, editorial look. Fonts Fraunces (headings) + Inter (body). Palette: ink `#1f1b16`, background `#f7f3ec`, card `#fffdf9`, accent `#b4532a`, sage `#dfe6d6`. Fully responsive and accessible (labels, focus states, alt text, keyboard navigation).
- Product images: no copyrighted brand imagery. Use `image_url` fields (royalty-free photos or generated placeholders); admins can change them.
- Tests: pytest for the backend (models, pricing, checkout webhook, auth, order lookup). Add tests with each phase. Run them before saying a phase is done.
- Never commit secrets. Stripe keys, database URLs and the agent key come from environment variables.

## Seed data
`backend/seed/` contains `products.json` (20 products, 217 variants), `orders.json` (12 demo orders) and `policies.json`.
Order dates are relative (`created_days_ago`, `delivered_days_ago`, `estimated_delivery_in_days`) — the seed script converts them to real dates at seed time so the demo never goes stale. Run `flask seed --reset` to rebuild demo data. Demo orders are guest orders (no user account) using the emails in the file.

## Commands (keep these working)
- Backend: `cd backend && flask db upgrade && flask seed --reset && flask run` · tests: `pytest`
- Frontend: `cd frontend && npm run dev` · checks: `npm run lint && npm run build`
