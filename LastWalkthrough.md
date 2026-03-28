# Flowytics — Missing Parts Analysis
*Analysed: 2026-03-28 | 174 tests passing | Sprint 7 in progress*

---

## Legend
| Symbol | Meaning |
|--------|---------|
| 🔴 | Blocking — breaks a user journey or loses money |
| 🟡 | Important — degrades experience or creates risk |
| 🟢 | Polish / nice-to-have |
| ⬜ | Explicitly out-of-scope for MVP (post-launch roadmap) |

---

## 1. Backend — Business Logic Gaps

### 🔴 Financial context never injected into the agent

**File:** `slack_agent_runner.py` → `agent/graph.py`

The `AgentState` has a `financial_summary` field, and `call_model` reads `state.get("financial_summary")`. But `process_slack_message` only passes `{"messages": [...]}` to `agent_app.ainvoke()` — it never loads QBO data from the DB and injects it into state. The agent therefore always operates with `financial_summary = None`. Every tool call the agent makes must re-derive data from scratch from the QBO snapshot every time, and the system prompt cash balance line is always skipped.

**Impact:** The agent's system prompt financial context is always blank.

---

### 🔴 Subscription never enforced at the API level

The `Tenant.subscription_status` field exists and Stripe webhooks update it correctly (`active`, `past_due`, `cancelled`). But **no endpoint or middleware checks whether the tenant is on a valid subscription** before serving requests. A `cancelled` or `past_due` tenant can still call `/quickbooks/sync`, get Slack responses, and trigger monthly reports indefinitely.

**Files:** All of `api/v1/`, `slack_agent_runner.py`, `proactive_alerts.py`

---

### 🔴 Trial expiry never enforced

`Tenant.trial_ends_at` is set in the model but **nothing in the codebase reads it**. There's no scheduled job or middleware that transitions a tenant from `trial → cancelled` when the trial period expires. A user who signs up but never pays will receive the service forever.

**Files:** `models/tenant.py` (field exists), `services/` (no job)

---

### 🟡 No "payment failed → Slack warning" notification

Sprint 6 explicitly lists: *"Graceful degradation: Stripe payment fail → past_due + Slack warning"* as `[ ]` (incomplete). When `invoice.payment_failed` fires, the tenant status is updated to `past_due` in the DB, but **no Slack message is sent** to inform the founder their payment failed.

**File:** `api/v1/stripe.py` line 105–116

---

### 🟡 Sync saves new snapshots without deduplication

Every call to `sync_tenant()` creates 3 new `FinancialSnapshot` rows (P&L, BS, CF). Old snapshots are never replaced or cleaned up. Running daily syncs for a year would produce 1,095 rows per tenant for the same 12-month period. The monthly report and agent only query `limit(1)` on the latest, so functionally correct, but the table grows unboundedly.

**File:** `services/sync.py` lines 48–76

---

### 🟡 Proactive alerts have no per-tenant deduplication

`run_proactive_alerts()` fires every morning and will send the same critical alert every single day as long as the condition persists (e.g., a startup sitting at 3 months runway for weeks). There is no "last alerted at" tracking per tenant per alert type.

**File:** `services/proactive_alerts.py`

---

### 🟡 `financial_summary` tool is not in the agent's tool list

`parse_qbo_to_financial_summary` exists in `tools/financial_summary.py` but is **not registered** in `agent/graph.py`'s `active_tools` list. The agent cannot call it. The 7 registered tools are: burn_rate, runway, cash_forecast, anomaly, scenario, fundraising, monthly_report.

**File:** `agent/graph.py` lines 19–27

---

### 🟡 `SlackUserMap` is created but never read for personalization

`SlackUserMap` rows are created in `slack_agent_runner.py` when a new Slack user messages the bot. But the runner never reads back the map to look up the Clerk user identity, meaning the agent can never resolve a Slack user to a specific Clerk user for per-user permissions or attribution.

**File:** `services/slack_agent_runner.py` lines 107–113

---

### 🟡 No `/sync` slash command in Slack

`_check_qbo_data_freshness()` tells users: *"Trigger a fresh sync with `/sync`"* but there is no Slack slash command `/sync` registered anywhere. Clicking that instruction does nothing.

**Files:** `services/slack_agent_runner.py` line 63, `api/v1/slack.py`

---

## 2. Frontend Gaps

### 🔴 No dashboard data — the dashboard is static

`frontend/src/app/dashboard/page.tsx` (6 KB) exists, but based on the directory structure there are no API calls wiring it to real backend data (burn rate, runway, cash forecast). The frontend components (`QuickBooksConnectButton`, `SlackConnectButton`, `StripeCheckoutButton`) are wired to the API, but the dashboard itself appears to be a static UI without live financial metrics.

---

### 🟡 Onboarding is missing the "bank" step

The sprint plan specifies a 5-step wizard: `Clerk → Stripe → QBO → Bank → Slack → Done`. The `onboarding/` directory has only 3 sub-directories: `accounting/`, `payment/`, `slack/`. The **bank/Plaid step page does not exist** (even as a skippable placeholder).

**Path:** `frontend/src/app/onboarding/` (missing `bank/`)

---

### 🟡 No subscription gating on the frontend

There is no UI state handling for `past_due` or `cancelled` subscription status. A user whose card fails sees no banner, no warning, no CTA to update payment.

---

### 🟡 Next.js middleware proxy deprecation (open sprint item)

Sprint 6 explicitly lists: *"Next.js middleware → proxy migration (deprecation fix)"* as `[ ]`. The current `middleware.ts` uses `clerkMiddleware` from `@clerk/nextjs/server` which is correct, but the broader proxy pattern for API forwarding may need review.

**File:** `frontend/src/middleware.ts`

---

## 3. Testing Gaps

### 🟡 No tests for `services/sync.py`

`sync_tenant()` is a critical integration path (QBO pull → DB write → status update) with zero dedicated tests. The closest coverage is the E2E test which mocks it.

---

### 🟡 No tests for `services/monthly_report.py`

`run_monthly_reports()` is a CRON job that calls Claude and sends Slack messages. It has no unit test on the orchestration logic (snapshot loading, LLM call, fallback on JSON parse error, Slack dispatch).

---

### 🟡 No API integration tests for Stripe webhooks

`test_api/` only has `test_health.py` and `test_api_auth.py`. The Stripe webhook handler (`POST /stripe/webhook`) which updates subscription status has no test.

---

### 🟡 Agent graph has only 1 test file

`test_agent/test_graph.py` covers the graph topology but the `cross_validate.py` and `select_model.py` modules have no dedicated tests.

---

### 🟢 No frontend tests at all

No Jest, Playwright, or Cypress tests exist. Sprint 7 lists *"Frontend smoke tests"* as `[ ]`.

---

## 4. Infrastructure / Operations Gaps

### 🟡 No database migration system

There is no Alembic setup. Schema changes currently require manual Supabase SQL execution. The sprint plan acknowledges this as a post-MVP item, but the project is at a stage where even minor model changes (new columns added this sprint) have no migration trail. If the production DB needs a new column, it must be done manually.

---

### 🟡 No error monitoring (Sentry / equivalent)

Structured logging is in place, but there is no external error tracking. If the production server crashes, a CRON job silently fails, or Claude returns an error at 3am, there is no alert. Sprint 7 lists *"Error monitoring: structured logging review"* as `[ ]`.

---

### 🟡 No rate limiting on any endpoint

Sprint 7 lists *"API endpoint'lerinde rate limiting"* as `[ ]`. Currently any unauthenticated actor can hammer `/api/v1/slack/events` (the Bolt webhook endpoint) or the health endpoint without any throttling. The Bolt handler does verify Slack request signatures, which is a strong control, but other endpoints have no protection.

---

### 🟡 JWT state tokens use a truncated Clerk key (`[:32]`)

Both QBO and Slack OAuth flows encode/decode JWT state tokens using `settings.CLERK_SECRET_KEY[:32]`. Clerk secret keys start with `sk_live_` or `sk_test_` — the first 32 chars include the prefix, not real entropy. This should use a dedicated `JWT_STATE_SECRET` env var.

**Files:** `api/v1/quickbooks.py` line 39, `api/v1/slack.py` line 48

---

### 🟡 Railway deployment is a single webhook — no health check

`deploy.yml` sends a `curl POST` to `$RAILWAY_DEPLOY_WEBHOOK_URL` but does not verify the deployment succeeded. No `/health` poll after deploy, no rollback on failure.

**File:** `.github/workflows/deploy.yml`

---

### 🟢 `ruff_report.txt` is committed to git

There's a `ruff_report.txt` in the project root. Linter output files should be ephemeral and not tracked in git.

---

## 5. Documentation Gaps

### 🟡 Sprint reports (`docs/sprints/`) do not exist

The weekly ritual document says: *"Claude Code ile sprint raporu üret (`docs/sprints/SPRINT_W{N}.md`)"* — but this directory has never been created. There are 7+ sprints with no persisted retrospective.

---

### 🟢 `README.md` is sparse

`README.md` (3.2 KB) exists but lacks: local dev setup instructions, environment variable reference (now solved by `.env.example`), how to run tests, and architecture overview.

---

## Summary Table

| Area | 🔴 Blocking | 🟡 Important | 🟢 Polish |
|------|------------|-------------|----------|
| Backend Logic | 3 | 5 | 0 |
| Frontend | 1 | 3 | 0 |
| Testing | 0 | 4 | 1 |
| Infrastructure | 0 | 4 | 1 |
| Docs | 0 | 1 | 1 |
| **Total** | **4** | **17** | **3** |

---

## Top 5 by Impact/Effort (Recommended Next)

1. **🔴 Financial context injection into agent** — highest impact, 1 file change
2. **🔴 Trial/subscription enforcement** — without this you ship a free product
3. **🟡 Alert deduplication** — prevents spamming founders every morning
4. **🟡 Stripe payment failed → Slack warning** — explicitly in sprint plan, closes an open item
5. **🟡 JWT state token entropy** — quick security fix, `[:32]` of `sk_live_` is weak

