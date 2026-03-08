# Flowytics — Agentic CFO

AI-powered managerial accounting intelligence layer for pre-seed and seed-stage US startups. Reads financial data from existing accounting software and banking sources, delivers proactive CFO-level insights via Slack.

**Core distinction:** Accounting software (QBO, Xero) does financial accounting — recording, categorizing, tax compliance. Flowytics does managerial accounting — analysis, forecasting, decision support for founders. We read their data, we don't replace their tools.

**Tagline:** "Your accounting software has the data. You're missing the CFO."

## Vision & Mission

**Vision:** A world where everyone can start a company and no one has to manage a backoffice.

**Mission:** Eliminate the mandatory friction of running a company — so talented people everywhere can create their own value.

**MVP Goal:** Delay the need for a fractional CFO ($1,500/mo) by providing 80% of the analytical value at $150/mo via Slack.

## Tech Stack

### Backend
- **Runtime:** Python 3.12, managed with `uv`
- **Framework:** FastAPI + Uvicorn
- **ORM:** SQLModel (Pydantic + SQLAlchemy, async via asyncpg)
- **Agent orchestration:** LangGraph
- **LLM:** Claude API — Opus 4.6 (rare/complex), Sonnet 4.5 (primary), Haiku 4.5 (Slack chat)
- **Data processing:** Polars (Rust-based DataFrame library)
- **JSON:** orjson (Rust-based, default serializer)
- **Scheduler:** APScheduler (in-process, cron-style jobs)
- **Auth:** Clerk (JWT verification)
- **Payments:** Stripe
- **Integrations:** Codat (accounting, via httpx wrapper — no SDK), Plaid (banking, optional), Slack Bot API

### Frontend
- **Framework:** Next.js (App Router, TypeScript strict)
- **Styling:** Tailwind CSS + shadcn/ui
- **Auth:** Clerk React components
- **Scope:** Onboarding wizard ONLY. No web dashboard. Post-onboarding = Slack.

### Infrastructure
- **Backend:** Railway (single service — API + Slack + Scheduler in one process)
- **Frontend:** Vercel
- **Database:** Supabase (managed PostgreSQL, direct connection via asyncpg)

## Project Structure

```
flowytics/
├── CLAUDE.md                     # This file — read first every session
├── pyproject.toml
├── uv.lock
├── backend/
│   ├── app/
│   │   ├── main.py               # FastAPI app + scheduler startup
│   │   ├── config.py             # pydantic-settings
│   │   ├── auth.py               # Clerk JWT middleware
│   │   ├── database.py           # SQLModel engine + session
│   │   ├── api/v1/               # API routes (see backend.md)
│   │   ├── agent/                # LangGraph CFO agent (see agents.md)
│   │   ├── tools/                # Deterministic financial tools (see agents.md)
│   │   ├── integrations/         # Codat, Plaid, Slack, Stripe clients
│   │   ├── models/               # SQLModel DB models + Pydantic schemas
│   │   ├── services/             # Business logic, sync, scheduler
│   │   └── prompts/              # Plain text LLM prompt files
│   └── tests/                    # See testing.md
├── frontend/                     # See frontend.md
│   ├── src/app/                  # Next.js pages
│   ├── src/components/
│   └── src/lib/
├── docs/
│   ├── architecture.md           # System overview, integrations, deployment
│   ├── backend.md                # Python conventions, FastAPI patterns
│   ├── agents.md                 # LangGraph agent, tools, model routing
│   ├── db.md                     # Schema, RLS, migrations, indexes
│   ├── frontend.md               # Onboarding flow, Clerk, Stripe
│   └── testing.md                # Test strategy, coverage, sprint reports
└── alembic/                      # DB migrations (post-MVP)
```

## Software Engineering Principles

### KISS — Keep It Simple, Stupid
- Single FastAPI process handles API + Slack + Scheduler. No microservices.
- Single LangGraph agent with tools. No multi-agent orchestration.
- Plain text prompt files. No prompt frameworks (no DSPy).
- Solve today's problem. Don't architect for 10,000 tenants when you have 0.

### DRY — Don't Repeat Yourself
- SQLModel models serve as both DB schema AND Pydantic validation models.
- One data flow path: Integration → DB → Tools → LLM → Slack. No parallel paths.
- Shared utility functions in `utils/`. No copy-paste across modules.

### SOLID
- **S — Single Responsibility:** Each tool does one calculation. Each API route handles one resource.
- **O — Open/Closed:** Tools are extendable (add new tools) without modifying the agent graph.
- **L — Liskov:** All tools follow the same interface: typed input → typed output.
- **I — Interface Segregation:** Lean Pydantic models per endpoint. No god-objects.
- **D — Dependency Inversion:** Agent depends on tool interfaces, not concrete implementations. Integrations accessed via abstract clients.

### YAGNI — You Aren't Gonna Need It
- No web dashboard until customer feedback demands it.
- No Xero support until QBO is proven (Codat abstracts this anyway).
- No multi-currency until a customer needs it.
- No Alembic migrations until schema changes become frequent.

### Lean Startup
- Ship the smallest thing that delivers value. Validate with real users.
- Every feature must answer: "Does this help a founder make a better financial decision?"
- If the answer is "maybe later" — it's not in MVP.

## ⛔ DESTRUCTIVE OPERATION WARNINGS

**NEVER do these without explicit human confirmation:**

```
DATABASE:
- NEVER DROP or TRUNCATE tables
- NEVER DELETE columns from existing tables
- NEVER run DELETE without WHERE clause
- NEVER modify production data directly
- ALWAYS back up before schema changes
- ALWAYS test SQL on sandbox/local before production

CREDENTIALS & SECRETS:
- NEVER delete or overwrite .env files
- NEVER log API keys, tokens, or secrets to console/files
- NEVER commit .env or credentials to git
- NEVER revoke OAuth tokens without user consent

GIT:
- NEVER force push to main branch
- NEVER delete remote branches without confirmation
- NEVER rebase shared branches

INTEGRATIONS:
- NEVER delete Codat/Plaid connections without user consent
- NEVER delete Stripe subscriptions programmatically without confirmation
- NEVER remove Slack bot from workspace without warning

FILE SYSTEM:
- NEVER rm -rf on project directories
- NEVER overwrite migration files
- NEVER delete test data fixtures
```

**When in doubt: ASK. A 30-second confirmation saves hours of recovery.**

## Commands

### Backend
```bash
uv sync                                    # Install dependencies
uv run fastapi dev backend/app/main.py     # Dev server
uv run pytest                              # All tests
uv run pytest tests/test_tools/ -v         # Tool tests only
uv run ruff check .                        # Lint
uv run mypy backend/                       # Type check
uv add <package>                           # Add dependency (NEVER pip)
```

### Frontend
```bash
cd frontend && npm install                 # Install deps
cd frontend && npm run dev                 # Dev server (port 3000)
cd frontend && npm run build               # Production build
cd frontend && npm run lint                # Lint
```

### CI/CD
- GitHub Actions runs on every push to `main` and `develop`
- CI: lint → type check → tool tests → API tests → coverage
- Deploy: manual trigger via `workflow_dispatch` (end of each sprint week)
- See `docs/testing.md` for full pipeline config

## Environment Variables

```env
# Clerk
CLERK_SECRET_KEY=
NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=

# Database (Supabase Postgres direct connection)
DATABASE_URL=postgresql+asyncpg://postgres:[password]@[host]:5432/postgres

# Anthropic
ANTHROPIC_API_KEY=

# Codat
CODAT_API_KEY=
CODAT_BASE_URL=

# Plaid
PLAID_CLIENT_ID=
PLAID_SECRET=
PLAID_ENV=sandbox

# Stripe
STRIPE_SECRET_KEY=
STRIPE_WEBHOOK_SECRET=

# Slack
SLACK_BOT_TOKEN=
SLACK_SIGNING_SECRET=
SLACK_APP_TOKEN=
```

## Critical Rules (Universal)

1. **NEVER use pip.** `uv add` only.
2. **NEVER use float for money.** `Decimal` everywhere.
3. **NEVER use DSPy.** Plain text prompts in `/prompts`.
4. **NEVER skip type hints.** Every function, every return.
5. **NEVER call LLM for arithmetic.** Deterministic tools only.
6. **NEVER query DB without tenant scope.** Every query filters by `tenant_id`.
7. **NEVER expose secrets.** pydantic-settings + .env only.
8. **Tools are the source of truth for numbers.** If LLM contradicts a tool, the tool wins.
9. **Codat is the accounting abstraction.** No direct QBO/Xero API unless Codat is blocked.
10. **Slack is the product.** Web UI exists only for onboarding.
11. **Graceful degradation always.** When a dependency fails, degrade — don't crash. See `docs/architecture.md` → Graceful Degradation Policy.

## Documentation Map

| File | Covers | Read when... |
|------|--------|--------------|
| `CLAUDE.md` | Vision, principles, rules, structure | Every session start |
| `docs/architecture.md` | System overview, integrations, deployment, costs | Designing new features, integration work |
| `docs/backend.md` | Python conventions, FastAPI patterns, data processing | Writing backend code |
| `docs/agents.md` | LangGraph agent, all tool specs, model routing | Working on agent or tools |
| `docs/db.md` | Full schema, RLS, indexes, data principles | Database work |
| `docs/frontend.md` | Onboarding flow, Clerk/Stripe/Codat/Plaid embeds | Frontend work |
| `docs/testing.md` | Test strategy, coverage goals, sprint reports | Writing tests, sprint reviews |

## When Compacting

Always preserve:
- List of modified files in this session
- Current sprint week number
- Current feature being built
- Test results from this session
- Any tool definitions in progress
- Unresolved errors or blockers

# Windows'ta bu kullan (fastapi-cli emoji bug'ı yüzünden)
uv run uvicorn backend.app.main:app --reload