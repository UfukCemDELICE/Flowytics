# Flowytics — Agentic CFO

Agentic Backoffice as a Service. AI-powered CFO that replaces fractional CFOs for early-stage startups. Orchestrates existing tools (QuickBooks, banks) instead of replacing them.

## Tech Stack

### Backend (Python — `uv` managed)
- **Runtime:** Python 3.12
- **Package manager:** `uv` (all dependencies via `uv add`, no pip)
- **Framework:** FastAPI + Uvicorn
- **AI/Agent:** LangGraph (orchestration + deterministic tools) + DSPy (prompt optimization/modular LLM calls)
- **LLM Models (Anthropic):**
  - Claude Opus → Advanced financial reasoning, complex analysis
  - Claude Sonnet → Document and report generation
  - Claude Haiku → Slack conversations, quick responses
- **Auth:** Clerk (user management, org management, JWT)
- **Database:** Supabase (PostgreSQL, database only — no Supabase Auth)
- **Cache:** Supabase `qb_cache` table with TTL
- **Async Jobs:** FastAPI BackgroundTasks
- **Payments:** Stripe
- **Data Source:** QuickBooks Online API via `python-quickbooks`
- **Messaging:** Slack (Bot API for conversational CFO)
- **Observability:** LangSmith

### Frontend
- **Framework:** Next.js 14+ (App Router)
- **Language:** TypeScript (strict mode)
- **Styling:** Tailwind CSS
- **Auth:** Clerk (React components + middleware)
- **Hosting:** Vercel

### Infrastructure
- **Backend hosting:** Railway
- **Database:** Supabase (managed PostgreSQL)

## Project Structure

```
flowytics/
├── CLAUDE.md
├── pyproject.toml
├── uv.lock
├── backend/
│   ├── app/
│   │   ├── main.py             # FastAPI entrypoint
│   │   ├── config.py           # Settings via pydantic-settings
│   │   ├── auth.py             # Clerk JWT verification middleware
│   │   ├── api/
│   │   │   └── v1/
│   │   │       ├── reports.py  # Financial reporting endpoints
│   │   │       ├── cashflow.py # Cash flow endpoints
│   │   │       ├── expenses.py # Expense management endpoints
│   │   │       ├── quickbooks.py # QB OAuth + webhook endpoints
│   │   │       └── slack.py    # Slack event handler
│   │   ├── agents/
│   │   │   ├── orchestrator.py # LangGraph agent graph
│   │   │   ├── financial_reporting.py
│   │   │   ├── cashflow.py
│   │   │   └── expense.py
│   │   ├── tools/
│   │   │   ├── ratios.py       # Financial ratio calculations
│   │   │   ├── runway.py       # Burn rate, runway, cash projections
│   │   │   ├── budget.py       # Budget vs actual, variance analysis
│   │   │   ├── anomaly.py      # Z-score anomaly detection
│   │   │   └── validators.py   # Cross-validation (tool output vs LLM output)
│   │   ├── integrations/
│   │   │   ├── quickbooks.py   # QuickBooks API client
│   │   │   ├── stripe.py       # Stripe billing
│   │   │   └── slack.py        # Slack Bot client
│   │   ├── models/             # Pydantic models + DB schemas
│   │   ├── services/
│   │   │   ├── financial.py    # Business logic layer
│   │   │   └── cache.py        # QuickBooks data cache (Supabase-backed)
│   │   └── utils/
│   └── tests/
│       ├── test_tools/         # Deterministic tool tests
│       ├── test_agents/        # Agent integration tests
│       └── test_api/           # API endpoint tests
├── frontend/
│   ├── src/
│   │   ├── app/                # Next.js App Router pages
│   │   ├── components/
│   │   ├── lib/                # API client, utils, Supabase client
│   │   └── types/
│   ├── middleware.ts            # Clerk auth middleware
│   ├── package.json
│   └── tsconfig.json
└── docs/
    └── architecture.md
```

## Commands

### Backend
- `uv sync`: Install all dependencies
- `uv run fastapi dev backend/app/main.py`: Start dev server
- `uv run pytest`: Run all tests
- `uv run pytest tests/test_tools/ -v`: Run deterministic tool tests only
- `uv add <package>`: Add dependency (NEVER use pip)

### Frontend
- `cd frontend && npm install`: Install deps
- `cd frontend && npm run dev`: Start Next.js dev server (port 3000)
- `cd frontend && npm run build`: Production build
- `cd frontend && npm run lint`: Lint check

## Architecture Principles

### Multi-Model Strategy
Each model is used where it excels. Never use a heavier model when a lighter one suffices:
- **Opus:** Complex financial reasoning — multi-step analysis, cross-statement insights, strategic recommendations. Used sparingly (expensive).
- **Sonnet:** Report generation, document creation, structured financial summaries. Primary workhorse.
- **Haiku:** Slack bot responses, quick Q&A, status checks. Fast and cheap for conversational UI.

Model selection is handled by the Orchestrator based on task complexity, NOT by the user.

### Deterministic Tools + LLM — Separation of Concerns
Every financial operation flows through the Orchestrator (LangGraph) which routes tasks:
1. **Deterministic tasks → LangGraph Tools:** All calculations, rule checks, threshold alerts, ratio computations. Pure Python functions, no LLM. These MUST be exact, reproducible, and auditable.
2. **Interpretive tasks → Claude (via DSPy modules):** Trend analysis, natural language summaries, forecasting, anomaly contextualization. Claude receives tool outputs as grounding context.
3. **Cross-validation:** If Claude's numeric outputs contradict tool results, always trust the tools. Flag discrepancies in logs.

### Tool Design Rules
- Every tool is a pure function: same input → same output, always.
- Every tool has comprehensive Pydantic input/output models.
- Every tool has unit tests with known financial data.
- Tools NEVER call the LLM. LLM NEVER does arithmetic.
- Tools are the moat foundation — the financial rule set grows with every customer.

### Role Separation — DSPy vs LangGraph
- **LangGraph:** Agent graph, state management, task routing, tool orchestration. Controls the FLOW.
- **DSPy:** Prompt optimization, modular LLM calls, structured outputs. Controls the QUALITY of each LLM interaction.
- These do NOT overlap. LangGraph calls DSPy modules as nodes within the graph.

### Auth Flow
- **Frontend:** Clerk React components handle sign-up/sign-in/org management.
- **Backend:** Clerk JWT verified on every request via FastAPI middleware in `auth.py`. User ID extracted from JWT claims.
- **Database:** Supabase tables use `clerk_user_id` column. RLS policies filter by this ID.
- Clerk and Supabase are NOT connected via Supabase Auth. Clerk is the single source of truth for identity.

### Slack Integration
- Slack Bot receives messages via Events API → FastAPI `/api/v1/slack/events`
- Bot identifies user via Slack-to-Clerk mapping in DB
- Uses Haiku for fast conversational responses
- Can trigger full analysis (upgrades to Sonnet/Opus) on request
- Responds in-thread with financial summaries, alerts, answers

### Data Caching Strategy
- QuickBooks data is cached in Supabase `qb_cache` table with `updated_at` timestamp
- Cache TTL: 1 hour for financial statements, 15 min for real-time data
- Cache check: query `qb_cache` first, hit QuickBooks API only if stale or missing
- Long-running agent tasks use FastAPI BackgroundTasks, results written to Supabase, frontend polls for completion

### Data Flow
```
QuickBooks API → Supabase Cache → Orchestrator → [Tools | Opus/Sonnet/Haiku] → Merged Output → API / Slack
```

## MVP Features

1. **Financial Reporting** — P&L, Balance Sheet, Cash Flow Statement analysis with KPIs
2. **Cash Flow Management & Forecasting** — Runway calculation, burn rate, 3-6 month projections
3. **Expense Management** — Budget vs actual, anomaly detection, category analysis
4. **Slack Bot** — Conversational access to all three features above

## Critical Rules

- **NEVER hardcode API keys.** Use environment variables via pydantic-settings.
- **NEVER use pip.** All Python packages managed through `uv`.
- **All financial calculations go through deterministic tools**, not LLM. No exceptions.
- **QuickBooks data must be cached in Supabase `qb_cache` table.** Never call QB API on every request.
- **Type hints on every function.** Use Pydantic models for all data boundaries.
- **Every tool must have a corresponding test** in `tests/test_tools/`.
- **Use the right model for the task.** Don't send Slack chat to Opus or complex analysis to Haiku.
- **Clerk is the auth source of truth.** Never store passwords or manage sessions manually.
- **API versioning:** All routes under `/api/v1/`. Never serve unversioned endpoints.

## Environment Variables

```
# Clerk
CLERK_SECRET_KEY=
NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=

# Supabase (database only)
SUPABASE_URL=
SUPABASE_SERVICE_ROLE_KEY=

# Anthropic
ANTHROPIC_API_KEY=

# QuickBooks
QB_CLIENT_ID=
QB_CLIENT_SECRET=
QB_REDIRECT_URI=
QB_ENVIRONMENT=sandbox

# Stripe
STRIPE_SECRET_KEY=
STRIPE_WEBHOOK_SECRET=

# Slack
SLACK_BOT_TOKEN=
SLACK_SIGNING_SECRET=

# LangSmith
LANGCHAIN_TRACING_V2=true
LANGCHAIN_API_KEY=
LANGCHAIN_PROJECT=flowytics
```

## When Compacting

Always preserve: list of modified files, current feature being built, test results, and any tool definitions in progress.
