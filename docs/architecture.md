# Architecture

## System Context (C4 Level 1)

```
                    👤 Startup Founder
                         ↕ Slack API
              ┌──────────────────────┐
              │  Flowytics (Agentic  │
              │     CFO System)      │
              └──────┬───────┬───────┘
                     │       │
              Codat API    Plaid API
                     │       │
              ┌──────┘       └──────┐
        Accounting Software    Bank Accounts
        (QBO, Xero)           (Chase, SVB, Mercury)
```

Flowytics is a read-only intelligence layer. It never writes back to accounting software or banks.

## Container Architecture (C4 Level 2)

Single backend process. No microservices.

```
┌─────────────────────────────────────────────────────┐
│                  Vercel                               │
│           Next.js Frontend                            │
│    (Onboarding UI only — signup, connect, done)       │
└──────────────────┬────────────────────────────────────┘
                   │ REST API calls
┌──────────────────▼────────────────────────────────────┐
│              Railway (Single Service)                   │
│                                                        │
│  ┌──────────────────────────────────────────────────┐  │
│  │              FastAPI Process                       │  │
│  │                                                    │  │
│  │  ├── REST API (onboarding, webhooks, health)       │  │
│  │  ├── Slack Bolt (mounted via ASGI adapter)         │  │
│  │  ├── APScheduler (daily sync, monthly reports)     │  │
│  │  └── LangGraph Agent (invoked by above three)      │  │
│  └──────────────────────┬───────────────────────────┘  │
└─────────────────────────┼──────────────────────────────┘
                          │
           ┌──────────────▼──────────────┐
           │   Supabase (Managed Postgres) │
           │   Direct connection via asyncpg│
           │   RLS enabled as safety net    │
           └────────────────────────────────┘

External APIs:
  → Anthropic Claude API (LLM reasoning)
  → Codat API (accounting data)
  → Plaid API (banking data)
  → Slack API (messaging)
  → Stripe API (billing)
  → Clerk API (auth verification)
```

## Data Flow

### Flow 1 — Onboarding
```
Clerk Sign Up → Stripe Payment Setup (14-day trial) →
Codat Link (connect QBO) → Plaid Link (connect bank, optional) →
Slack OAuth (add bot) → Initial data sync triggered →
First CFO report sent to Slack within 24h
```
Details: see frontend.md

### Flow 2 — Daily Sync (Scheduled)
```
APScheduler triggers at 6am UTC for each active tenant
  → Codat: GET /companies/{id}/data/{type} → P&L, Balance Sheet, Transactions
  → Plaid: POST /transactions/sync → new transactions since last cursor
  → Raw JSONB saved to financial_snapshots table
  → At 7am: deterministic tools run (burn rate, runway, anomalies)
  → If critical threshold breached → immediate Slack alert
```

### Flow 3 — Founder Asks Question (Reactive via Slack)
```
Slack message → FastAPI webhook endpoint → acknowledge 200 OK immediately
  → Background task: identify user → load financial data from DB
  → LangGraph agent: select model → call tools → interpret → format
  → Post result to Slack thread
  → Log to agent_runs table
```

### Flow 4 — Monthly CFO Report (Proactive)
```
1st business day of month → scheduler triggers
  → All tools run for each tenant
  → Claude Sonnet generates executive summary
  → Block Kit formatted report posted to Slack
  → Founder can reply with follow-ups (triggers Flow 3)
```

## Integration Layer

### Codat — Accounting Data (Primary)

Normalized API for QBO + Xero + Sage + NetSuite. One integration, multiple platforms.

**MVP endpoints:**
| Endpoint | Returns | Used for |
|----------|---------|----------|
| `GET /data/profitAndLoss` | Revenue, expenses, net income | Burn rate, margins |
| `GET /data/balanceSheet` | Assets, liabilities, equity | Cash position, ratios |
| `GET /data/accounts` | Chart of accounts | Category mapping |
| `GET /data/bankTransactions` | Transaction detail | Anomaly detection |
| `GET /data/invoices` | Accounts receivable | Cash flow timing |
| `GET /data/bills` | Accounts payable | Cash flow timing |

**Sync:** Codat webhooks (DataSyncCompleted) for near real-time. Daily scheduled pull as fallback.

**Onboarding:** Codat Link UI embedded in frontend wizard. Handles OAuth.

**Fallback:** If Codat approval blocked >3 days, use `python-quickbooks` directly against QBO sandbox. Wrap behind same interface so switch is transparent.

**No Codat SDK in dependencies.** Codat's Python SDK is community-maintained and sometimes outdated. Instead, use `httpx` (already in deps) with a thin wrapper in `backend/app/integrations/codat.py`. Codat API is simple REST: auth header + GET. One file to maintain, no third-party SDK version to track.

### Plaid — Banking Data (Optional in MVP)

Codat already provides bank transaction data via QBO bank feeds. Plaid adds real-time balance checks (QBO can be hours stale).

**MVP endpoints:**
| Endpoint | Returns | Used for |
|----------|---------|----------|
| `GET /accounts/balance/get` | Real-time balances | Accurate cash position |
| `POST /transactions/sync` | Incremental feed | Cross-validation with Codat |

**Onboarding:** Plaid Link UI. Skippable — "Connect bank for real-time cash tracking."

### Slack — Primary Interface

Slack Bolt for Python mounted inside FastAPI via ASGI adapter. Socket Mode for dev, Events API for production.

**Channel:** `#flowytics-cfo` created during onboarding. DMs also supported.

**Message types:**
- **Proactive alert:** Threshold breach → immediate notification
- **Monthly report:** Block Kit sections for all metrics
- **Q&A response:** Natural language answer with data backing
- **Welcome:** "✅ Connected. First report in 24h."

**Critical constraint:** Slack requires 3-second acknowledgment. FastAPI endpoint returns 200 immediately, agent runs in BackgroundTasks.

### Stripe — Billing

Single product: **$150/mo, 14-day free trial.**

- Trial starts when first analysis runs successfully (value delivered)
- Stripe Checkout Session created during onboarding
- Webhook `customer.subscription.updated` → update tenant.subscription_status
- Customer Portal for self-service management

### Clerk — Auth

- Clerk Organizations = Tenants. One org = one startup.
- JWT verified on every backend request via middleware.
- `clerk_org_id` links to `tenants` table.
- No Supabase Auth. Clerk is the single source of truth for identity.

## Graceful Degradation Policy

The system must never fully stop. When dependencies fail, degrade gracefully:

| Failure | Impact | System Response |
|---------|--------|----------------|
| Codat connection lost | No fresh accounting data | Continue with last `financial_snapshots`. All Slack messages show "⚠️ Using data from {date}. Reconnect at app.flowytics.io" |
| Plaid connection lost | No real-time bank balance | Fall back to Codat's bank data (delayed but available). No user-facing warning unless Codat also down. |
| Stripe payment failed | Revenue at risk | `past_due` status. Service continues 14 days (Stripe smart retry). Slack warning sent. After 14 days → `cancelled`, final notice, agent stops. |
| Slack bot removed | Can't deliver insights | Agent completes analysis, saves to DB. Delivery marked failed. Pending reports queued. Delivered when Slack reconnected. |
| Claude API down | No LLM reasoning | Retry once. If fails: deliver tool results only (numbers without narrative). "AI analysis temporarily unavailable." |
| Database down | Total outage | 503 on all routes. Slack bot responds "Try again in a few minutes." No data corruption risk. |

**Principle:** Data is never lost. Analysis continues with stale data rather than stopping. User is always informed of degraded state.

Details and test specifications: see `docs/testing.md` → Graceful Degradation Tests.

## Deployment

### Railway — Single Backend Service
One Dockerfile, one process, one deploy. Contains:
- FastAPI API server
- Slack Bolt (ASGI mounted)
- APScheduler (starts on app startup)
- LangGraph agent (invoked by all above)

### Vercel — Frontend
Next.js static + SSR. Clerk middleware for auth. Minimal — 5 onboarding pages + settings.

### Supabase — Database
Managed PostgreSQL. Direct connection via asyncpg (not REST API). Connection pooler (PgBouncer) for production.

## Cost Estimate (MVP, 10 tenants)

| Item | Monthly Cost |
|------|-------------|
| Railway (single service) | $5-15 |
| Vercel (Pro) | $20 |
| Supabase (Pro) | $25 |
| Claude API (~10 tenants) | $50-150 |
| Codat (Startup tier) | $0-99 |
| Plaid (Development) | $0 |
| Clerk (Free tier) | $0 |
| Stripe (per txn) | 2.9% + 30¢ |
| **Total** | **~$100-310/mo** |

Revenue at 10 paying tenants: $1,500/mo. Positive unit economics from day one.

## Decisions Log

| Alternative | Why Rejected |
|-------------|--------------|
| Microservices (separate Slack/API/Scheduler) | Overkill for 10 tenants. Single process simpler to deploy, debug, maintain. |
| Multi-agent system | Single agent handles all tools. Multi-agent adds orchestration overhead with zero value at this scale. |
| Neuro-symbolic AI (PyReason) | Python 3.12 incompatible, months of R&D, solo founder can't afford. |
| DSPy for prompts | Zero experience, no training data. Plain text prompts for MVP. |
| Direct QBO API | Codat provides multi-platform abstraction. Direct only as fallback. |
| Codat Python SDK | Community-maintained, sometimes outdated. httpx wrapper is simpler and maintainable. |
| Supabase REST API (supabase-py) | Direct Postgres via SQLModel + asyncpg gives proper ORM, migrations, type safety. |
| Web dashboard | Slack-first. Dashboard adds frontend complexity without MVP value. |
| Türkiye market | Different accounting system, no Plaid/Codat, low payment capacity. |
| Fractional CFO B2B2C | $46-97M funded competitors, Botkeeper's $90M failure. |
| LangSmith observability | Paid service. Console logging + agent_runs table sufficient for MVP. |
| CI/CD post-MVP | Too risky. GitHub Actions CI set up in Week 1. Deploy via manual trigger per sprint. |
