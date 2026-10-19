# Architecture

This page shows the whole Kora Outfitters system on one page: what the parts are, and how a request moves
between them. It is updated after every phase.

**Status:** Phase 0 (backend half) is built. Everything marked *planned* comes in a later phase.

## The parts

| Part | What it is | Where it runs | Status |
|---|---|---|---|
| Browser | The customer's or admin's web browser | User's device | — |
| Next.js frontend (`frontend/`) | The website: pages, cart, checkout screens. It also **forwards** every `/api/...` request to Flask. | Vercel | *planned (Phase 0, frontend half)* |
| Flask backend (`backend/`) | The API: business rules, prices, stock, orders, auth. Returns JSON only. | Render | ✅ skeleton + `/api/health` |
| Postgres database | Stores products, orders, users, policies | Neon (prod), Docker (local) | ✅ running locally, no tables yet |
| Stripe | Takes card payments, then tells our backend with a **webhook** (a message Stripe sends to our server) | Stripe | *planned (Phase 4)* |
| AI support agent (`agent/`) | A LangGraph program that answers customer questions by calling `/api/agent/*` | Render | *planned (Phase 8)* |
| Groq / Gemini | Large language models (LLMs) the agent uses | Their clouds | *planned (Phase 8)* |

## System diagram

```mermaid
flowchart LR
    B[Browser]

    subgraph Vercel
        N[Next.js frontend<br/>pages + /api proxy]
    end

    subgraph Render
        F[Flask API<br/>blueprints under /api]
        A[AI agent<br/>LangGraph]:::planned
    end

    DB[(Postgres<br/>Neon / Docker)]
    S[Stripe]:::planned
    L[Groq + Gemini LLMs]:::planned

    B -- "every request goes to the<br/>same origin (one domain)" --> N
    N -- "rewrite /api/:path*<br/>to BACKEND_URL" --> F
    F -- "SQL via SQLAlchemy" --> DB
    F -. "create checkout session" .-> S
    S -. "webhook: payment done" .-> F
    N -. "chat messages" .-> A
    A -. "tools: /api/agent/*<br/>X-Agent-Key header" .-> F
    A -. "prompts" .-> L

    classDef planned stroke-dasharray: 5 5,opacity:0.7
```

Dashed lines and boxes are planned. Solid lines are the main path every request takes.

## How a request flows

Every request follows the same path. The browser never talks to Flask directly. It only talks to the
Next.js site, and Next.js forwards anything under `/api` to Flask.

```mermaid
sequenceDiagram
    participant B as Browser
    participant N as Next.js (Vercel)
    participant F as Flask (Render)
    participant D as Postgres

    B->>N: GET /api/health
    N->>F: GET {BACKEND_URL}/api/health (rewrite)
    F->>D: SELECT 1
    D-->>F: 1
    F-->>N: 200 {"status":"ok","database":"ok"}
    N-->>B: same response
```

**Why the proxy?** The site lives on `vercel.app` and the API on `onrender.com`. Those are two different
domains. If the browser called the API directly, we would need CORS rules (browser rules for cross-domain
requests), and our login cookie would be a "third-party" cookie, which many browsers block. With the proxy,
the browser only sees one domain. Cookies stay first-party and CORS is never needed.

## Inside the Flask backend

```mermaid
flowchart TB
    W[wsgi.py<br/>app = create_app] --> C[create_app]
    C --> CFG[config.py<br/>reads env vars]
    C --> EXT[extensions.py<br/>db, migrate]
    C --> ERR[errors.py<br/>JSON error handlers]
    C --> BP[api/__init__.py<br/>register blueprints at /api]
    BP --> H[health ✅]
    BP --> P[products]
    BP --> AU[auth]
    BP --> CA[cart]
    BP --> CH[checkout]
    BP --> O[orders]
    BP --> AD[admin]
    BP --> AG[agent]
```

Only `health` has routes so far. The other blueprints are empty and are filled in phases 2–8.

## Key rules (from CLAUDE.md)

- Money is stored as **integer cents** (`2999` means $29.99), never as floats.
- The backend recalculates every price. It never trusts prices from the browser.
- Stock goes down only when Stripe confirms payment (in the webhook).
- Every order status change writes a row to `order_events`.
- Store policies live in the database, so the website and the agent read the same text.
- `/api/agent/*` uses an `X-Agent-Key` header, not user cookies.
