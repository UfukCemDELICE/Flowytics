# Architecture

## System Context (C4 Level 1)

```
                    👤 Startup Founder
                         ↕ Slack API
              ┌──────────────────────┐
              │  Flowytics (Agentic  │
              │     CFO System)      │
               └──────┬───────────────┘
                      │
               QuickBooks API
                      │
               ┌──────┘
         Accounting Software
         (QBO, Xero)
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
  → QuickBooks API (accounting data)
  → Slack API (messaging)
  → Stripe API (billing)
  → Clerk API (auth verification)
```

## Data Flow

### Flow 1 — Onboarding
```
Clerk Sign Up → Stripe Payment Setup (14-day trial) →
QuickBooks OAuth (connect QBO) →
Slack OAuth (add bot) → Initial data sync triggered →
First CFO report sent to Slack within 24h
```
Details: see frontend.md

### Flow 2 — Daily Sync (Scheduled)
```
APScheduler triggers at 6am UTC for each active tenant
  → QuickBooks: Query Reports via API → P&L, Balance Sheet, Transactions
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

### QuickBooks — Accounting Data (Primary)

Direct integration via standard OAuth and QBO API.

**MVP endpoints:**
| Endpoint | Returns | Used for |
|----------|---------|----------|
| `ProfitAndLoss` | Revenue, expenses, net income | Burn rate, margins |
| `BalanceSheet` | Assets, liabilities, equity | Cash position, ratios |
| `Account` | Chart of accounts | Category mapping |
| `TransactionList` | Transaction detail | Anomaly detection |

**Sync:** Webhooks or daily scheduled pulls.
**Onboarding:** Direct QBO OAuth flow in the frontend wizard/dashboard.


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
| QuickBooks connection lost | No fresh accounting data | Continue with last `financial_snapshots`. All Slack messages show "⚠️ Using data from {date}. Reconnect via dashboard." |
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
| QuickBooks API | $0 (Free) |
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
| Direct QBO API | Decided to adopt direct integration after unresponsive experience with aggregators. |
| Web dashboard | Allowed strictly for onboarding and integration/billing management. No analytics reports (Slack-first). |
| Türkiye market | Different accounting system, low payment capacity. |
| Fractional CFO B2B2C | $46-97M funded competitors, Botkeeper's $90M failure. |
| LangSmith observability | Paid service. Console logging + agent_runs table sufficient for MVP. |
| CI/CD post-MVP | Too risky. GitHub Actions CI set up in Week 1. Deploy via manual trigger per sprint. |
