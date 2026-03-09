# Flowytics — Repository Snapshot

> Generated: 2026-03-09

---

## Project Overview

**Flowytics** is an AI-powered managerial accounting intelligence layer for pre-seed and seed-stage US startups. It reads financial data from accounting software (QuickBooks Online, Xero via Codat) and banking sources (Plaid), then delivers proactive CFO-level insights via Slack.

**Tagline:** *"Your accounting software has the data. You're missing the CFO."*

**MVP Goal:** Delay the need for a fractional CFO ($1,500/mo) by providing 80% of the analytical value at $150/mo via Slack.

---

## Tech Stack

### Backend
| Layer | Technology |
|---|---|
| Runtime | Python 3.12, managed with `uv` |
| Framework | FastAPI + Uvicorn |
| ORM | SQLModel (Pydantic + SQLAlchemy, async via asyncpg) |
| Agent orchestration | LangGraph |
| LLM | Claude API — Opus 4.6 (complex), Sonnet 4.5 (primary), Haiku 4.5 (Slack chat) |
| Data processing | Polars (Rust-based DataFrame) |
| JSON | orjson (Rust-based) |
| Scheduler | APScheduler (in-process cron-style) |
| Auth | Clerk (JWT verification) |
| Payments | Stripe |
| Accounting integration | Codat (QBO/Xero abstraction, via httpx) |
| Banking integration | Plaid (optional) |
| Messaging | Slack Bot API |

### Frontend
| Layer | Technology |
|---|---|
| Framework | Next.js 16 (App Router, TypeScript strict) |
| Styling | Tailwind CSS v4 + shadcn/ui |
| Auth | Clerk React components |
| Scope | Onboarding wizard ONLY — no web dashboard |

### Infrastructure
| Layer | Technology |
|---|---|
| Backend | Railway (single service — API + Slack + Scheduler) |
| Frontend | Vercel |
| Database | Supabase (managed PostgreSQL, asyncpg direct connection) |

---

## Main Entry Points

| Entry Point | Path | Purpose |
|---|---|---|
| Backend API server | `backend/app/main.py` | FastAPI app, scheduler startup, Slack bot init |
| App configuration | `backend/app/config.py` | pydantic-settings env var loading |
| Auth middleware | `backend/app/auth.py` | Clerk JWT verification |
| Database session | `backend/app/database.py` | SQLModel async engine + session factory |
| Slack integration | `backend/app/integrations/slack.py` | Slack Bot API client |
| Stripe integration | `backend/app/integrations/stripe.py` | Stripe billing client |
| LangGraph agent | `backend/app/agent/` | CFO agent graph definition |
| Financial tools | `backend/app/tools/` | Deterministic calculation tools |
| LLM prompts | `backend/app/prompts/` | Plain text prompt files |
| Frontend root | `frontend/src/app/page.tsx` | Next.js landing/onboarding root page |
| Frontend layout | `frontend/src/app/layout.tsx` | Root layout with Clerk provider |
| Frontend auth | `frontend/src/app/sign-in/`, `sign-up/` | Clerk auth pages |
| Frontend API client | `frontend/src/lib/api.ts` | HTTP client for backend |
| Frontend middleware | `frontend/src/middleware.ts` | Clerk auth middleware (route protection) |

---

## Project Tree

```
.
├── CLAUDE.md
├── README.md
├── backend
│   ├── app
│   │   ├── __init__.py
│   │   ├── agent
│   │   │   └── __init__.py
│   │   ├── api
│   │   │   ├── __init__.py
│   │   │   └── v1
│   │   │       └── __init__.py
│   │   ├── auth.py
│   │   ├── config.py
│   │   ├── database.py
│   │   ├── integrations
│   │   │   ├── __init__.py
│   │   │   ├── slack.py
│   │   │   └── stripe.py
│   │   ├── main.py
│   │   ├── models
│   │   │   ├── __init__.py
│   │   │   ├── agent_run.py
│   │   │   ├── computed_metric.py
│   │   │   ├── financial_snapshot.py
│   │   │   ├── integration.py
│   │   │   ├── slack_message.py
│   │   │   └── tenant.py
│   │   ├── prompts
│   │   │   └── __init__.py
│   │   ├── services
│   │   │   └── __init__.py
│   │   ├── tools
│   │   │   └── __init__.py
│   │   └── utils
│   │       └── __init__.py
│   └── tests
│       ├── __init__.py
│       ├── test_agent
│       │   └── __init__.py
│       ├── test_api
│       │   └── __init__.py
│       ├── test_models
│       │   ├── __init__.py
│       │   └── test_models.py
│       └── test_tools
│           └── __init__.py
├── docs
│   ├── agents.md
│   ├── architecture.md
│   ├── backend.md
│   ├── db.md
│   ├── frontend.md
│   ├── package-changes.md
│   ├── testing.md
│   └── REPO_SNAPSHOT.md          ← this file
├── frontend
│   ├── components.json
│   ├── eslint.config.mjs
│   ├── next.config.ts
│   ├── package.json
│   ├── package-lock.json
│   ├── postcss.config.mjs
│   ├── public
│   │   ├── android-chrome-192x192.png
│   │   ├── android-chrome-512x512.png
│   │   ├── apple-touch-icon.png
│   │   ├── favicon-16x16.png
│   │   ├── favicon-32x32.png
│   │   ├── favicon.ico
│   │   ├── file.svg
│   │   ├── globe.svg
│   │   ├── googleb01f1111b38cafb3.html
│   │   ├── llms.txt
│   │   ├── next.svg
│   │   ├── og-image.png
│   │   ├── robots.txt
│   │   ├── site.webmanifest
│   │   ├── sitemap.xml
│   │   ├── vercel.svg
│   │   └── window.svg
│   ├── src
│   │   ├── app
│   │   │   ├── globals.css
│   │   │   ├── layout.tsx
│   │   │   ├── page.tsx
│   │   │   ├── sign-in
│   │   │   │   └── [[...sign-in]]
│   │   │   │       └── page.tsx
│   │   │   └── sign-up
│   │   │       └── [[...sign-up]]
│   │   │           └── page.tsx
│   │   ├── lib
│   │   │   ├── api.ts
│   │   │   └── utils.ts
│   │   └── middleware.ts
│   └── tsconfig.json
├── pyproject.toml
└── uv.lock
```

---

## `pyproject.toml`

```toml
[project]
name = "flowytics"
version = "0.1.0"
description = "Add your description here"
readme = "README.md"
requires-python = ">=3.12"
dependencies = [
    "anthropic>=0.83.0",
    "apscheduler>=3.11.0",
    "asyncpg>=0.31.0",
    "clerk-backend-api>=5.0.2",
    "cryptography>=46.0.5",
    "fastapi[standard]>=0.129.2",
    "httpx>=0.28.1",
    "langchain-anthropic>=1.3.3",
    "langchain-core>=1.2.14",
    "langgraph>=1.0.9",
    "orjson>=3.11.7",
    "plaid-python>=29.0.0",
    "polars>=1.38.1",
    "pydantic-settings>=2.13.1",
    "pyjwt>=2.11.0",
    "python-dotenv>=1.2.1",
    "slack-bolt>=1.27.0",
    "slack-sdk>=3.40.1",
    "sqlmodel>=0.0.37",
    "stripe>=14.3.0",
    "uvicorn[standard]>=0.41.0",
]

[dependency-groups]
dev = [
    "mypy>=1.19.1",
    "pytest>=9.0.2",
    "pytest-asyncio>=1.3.0",
    "pytest-cov>=7.0.0",
    "ruff>=0.15.2",
]
```

---

## `frontend/package.json`

```json
{
  "name": "frontend",
  "version": "0.1.0",
  "private": true,
  "scripts": {
    "dev": "next dev",
    "build": "next build",
    "start": "next start",
    "lint": "eslint"
  },
  "dependencies": {
    "@clerk/nextjs": "^6.38.1",
    "@stripe/stripe-js": "^8.8.0",
    "class-variance-authority": "^0.7.1",
    "clsx": "^2.1.1",
    "lucide-react": "^0.576.0",
    "next": "16.1.6",
    "radix-ui": "^1.4.3",
    "react": "19.2.3",
    "react-dom": "19.2.3",
    "stripe": "^20.3.1",
    "tailwind-merge": "^3.5.0"
  },
  "devDependencies": {
    "@tailwindcss/postcss": "^4",
    "@types/node": "^20",
    "@types/react": "^19",
    "@types/react-dom": "^19",
    "eslint": "^9",
    "eslint-config-next": "16.1.6",
    "shadcn": "^3.8.5",
    "tailwindcss": "^4",
    "tw-animate-css": "^1.4.0",
    "typescript": "^5"
  }
}
```

---

## Data Flow

```
Accounting (QBO/Xero via Codat)
Banking (Plaid)
        │
        ▼
  [Sync Service]  ──► PostgreSQL (Supabase)
        │                    │
        │              financial_snapshot
        │              computed_metric
        │              tenant / integration
        │
        ▼
  [LangGraph CFO Agent]
        │
        ├── deterministic Tools (Polars calculations)
        └── Claude LLM (Sonnet 4.5 / Haiku 4.5)
                │
                ▼
           Slack Bot  ──► Founder's Slack DM
```

---

## DB Models (SQLModel)

| Model | File | Purpose |
|---|---|---|
| `Tenant` | `models/tenant.py` | Multi-tenant root entity |
| `Integration` | `models/integration.py` | Codat/Plaid connection per tenant |
| `FinancialSnapshot` | `models/financial_snapshot.py` | Raw P&L / balance sheet data |
| `ComputedMetric` | `models/computed_metric.py` | Derived KPIs (burn rate, runway, etc.) |
| `AgentRun` | `models/agent_run.py` | LangGraph execution audit log |
| `SlackMessage` | `models/slack_message.py` | Sent Slack message history |
