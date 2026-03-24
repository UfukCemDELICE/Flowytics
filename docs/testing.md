# Testing & Quality

## Test Strategy

Three test layers ordered by priority. If time is short, tools tests are non-negotiable. Everything else is best-effort during sprint.

### Layer 1 — Deterministic Tool Tests (CRITICAL)

Every financial calculation tool MUST have comprehensive tests. These are the foundation of trust. If a tool gives a wrong number, a founder makes a wrong decision.

**Location:** `backend/tests/test_tools/`
**Runner:** `uv run pytest tests/test_tools/ -v`

```
tests/test_tools/
├── test_burn_rate.py
├── test_runway.py
├── test_cash_forecast.py
├── test_anomaly.py
├── test_scenario.py
├── test_fundraising.py
└── conftest.py           # Shared fixtures: sample financial data
```

**Test categories per tool:**

1. **Happy path:** Standard startup financial data → expected output
2. **Edge cases:**
   - Zero revenue (pre-revenue startup)
   - Negative net burn (profitable company)
   - Single month of data (minimum viable input)
   - Very high burn (runway < 1 month)
   - Missing categories in data
3. **Boundary conditions:**
   - Runway exactly at threshold boundaries (3.0, 6.0, 12.0 months)
   - Z-score exactly at 2.0
   - Zero standard deviation (constant spend)
4. **Data integrity:**
   - Decimal precision (never float)
   - Empty input → graceful error, not crash
   - Negative amounts handled correctly
   - Currency consistency

**Example test:**

```python
from decimal import Decimal
from app.tools.runway import calculate_runway, RunwayResult

def test_runway_critical_threshold():
    result = calculate_runway(
        cash_balance=Decimal("50000"),
        monthly_net_burn=Decimal("20000")
    )
    assert result.runway_months == Decimal("2.5")
    assert result.runway_status == "critical"
    assert result.cash_zero_date is not None

def test_runway_zero_burn():
    """Profitable company — infinite runway."""
    result = calculate_runway(
        cash_balance=Decimal("100000"),
        monthly_net_burn=Decimal("-5000")  # negative burn = profit
    )
    assert result.runway_status == "healthy"
    assert result.runway_months is None  # infinite

def test_runway_decimal_precision():
    """Verify Decimal, not float."""
    result = calculate_runway(
        cash_balance=Decimal("33333.33"),
        monthly_net_burn=Decimal("10000.00")
    )
    assert isinstance(result.runway_months, Decimal)
    assert result.runway_months == Decimal("3.333333")  # exact, not 3.3333330000000001
```

### Layer 2 — API Endpoint Tests (IMPORTANT)

Test that API routes authenticate, validate input, and return correct responses.

**Location:** `backend/tests/test_api/`
**Runner:** `uv run pytest tests/test_api/ -v`

```
tests/test_api/
├── test_health.py
├── test_onboarding.py
├── test_webhooks.py
└── conftest.py          # FastAPI test client, mock auth
```

**What to test:**
- Unauthenticated request → 401
- Invalid JWT → 401
- Valid request → 200 + correct response shape
- Webhook signature verification
- Tenant isolation (user A can't access user B's data)

**Mock strategy:** Mock Clerk JWT verification in tests. Mock QuickBooks/Stripe/Plaid API calls. Never hit real external APIs in tests.

### Layer 3 — Agent Integration Tests (NICE TO HAVE)

Test the LangGraph agent end-to-end with mocked LLM responses.

**Location:** `backend/tests/test_agent/`
**Runner:** `uv run pytest tests/test_agent/ -v`

```
tests/test_agent/
├── test_graph.py        # Full graph execution with mock Claude
├── test_routing.py      # Model selection logic
└── test_validation.py   # Cross-validation logic
```

**Mock LLM:** Use a mock that returns predefined responses. Don't call Claude in tests — it's slow, expensive, and non-deterministic.

**What to test:**
- Slack message triggers correct model selection
- Tools are called in correct order
- Cross-validation catches discrepancies
- Output is properly formatted for Slack Block Kit

## Test Data

### Synthetic Financial Data

Create realistic but fake startup financial data in `tests/conftest.py`:

```python
import pytest
from decimal import Decimal

@pytest.fixture
def sample_pnl():
    """12 months of P&L for a typical seed-stage SaaS startup."""
    return {
        "months": [
            {"period": "2025-04", "revenue": Decimal("8000"), "expenses": Decimal("45000")},
            {"period": "2025-05", "revenue": Decimal("10000"), "expenses": Decimal("47000")},
            {"period": "2025-06", "revenue": Decimal("12000"), "expenses": Decimal("46000")},
            # ... 12 months
        ],
        "currency": "USD"
    }

@pytest.fixture
def sample_balance_sheet():
    """Balance sheet with $500K cash, typical seed-stage."""
    return {
        "cash": Decimal("500000"),
        "accounts_receivable": Decimal("15000"),
        "total_assets": Decimal("530000"),
        "accounts_payable": Decimal("12000"),
        "total_liabilities": Decimal("50000"),
        "total_equity": Decimal("480000"),
    }
```

### Startup Profiles for Testing

| Profile | Revenue | Monthly Burn | Cash | Runway | Useful for |
|---------|---------|-------------|------|--------|------------|
| Healthy SaaS | $50K MRR, growing 15% MoM | $80K | $1.2M | 15 months | Happy path |
| Pre-revenue | $0 | $35K | $200K | 5.7 months | Warning scenarios |
| Dying startup | $5K, flat | $60K | $120K | 2 months | Critical alerts |
| Profitable | $100K | $-20K (profit) | $500K | Infinite | Edge case |
| New startup | 1 month data | $10K | $50K | 5 months | Minimum data |

Create fixtures for each profile.

## Coverage Goals

Arbitrary percentages are misleading. Instead, coverage is defined by **what must be tested:**

### Tool Tests — Every Code Path (NON-NEGOTIABLE)
Every tool function must have tests covering:
- Every `if/else` branch
- Every threshold boundary (e.g., runway at exactly 3.0, 6.0, 12.0 months)
- Every error case (empty input, zero division, missing data)
- Decimal precision verification on every output

**Why non-negotiable:** A wrong burn rate calculation → founder makes a wrong hiring/firing/fundraising decision. This is the one thing that absolutely cannot be wrong. No tool ships without full path coverage.

Run: `uv run pytest tests/test_tools/ --cov=backend/app/tools --cov-report=term-missing`
If any line in `tools/` is uncovered, write a test for it before moving on.

### API Tests — Auth + Tenant Isolation (REQUIRED BEFORE LAUNCH)
Every API endpoint must have tests for:
- Unauthenticated request → 401
- Valid request → correct response shape
- Tenant isolation: user A cannot access user B's data

**Why required:** Auth bypass or tenant data leak = security incident. These tests are simple to write and prevent catastrophic bugs.

### Agent Tests — Routing + Validation (BEST EFFORT)
Model routing logic and cross-validation should be tested with mocked LLM responses. Nice to have, not blocking.

### Frontend Tests — Minimal Smoke Tests (REQUIRED BEFORE LAUNCH)
Not zero. Test these:
- Clerk middleware redirects unauthenticated users
- API wrapper handles 401/500 errors gracefully (shows error toast, doesn't crash)
- Onboarding stepper advances to correct step based on tenant state

Run: `cd frontend && npm run test` (add vitest or jest in Week 6)

No E2E tests (Cypress/Playwright) for MVP — third-party OAuth flows are impractical to mock in automated tests. First 5 customers onboarded with manual testing.

## Graceful Degradation Tests

These test what happens when things break. Critical for business continuity.

### QuickBooks/Plaid Connection Lost
**Test:** Mock QuickBooks API returning 403 (disconnected).
**Expected behavior:**
- System continues using last known `financial_snapshots`
- All tools run with stale data
- Every Slack message includes "⚠️ Using data from {last_sync_date}. Reconnect at app.flowytics.io"
- `integration.sync_status` set to `disconnected`
- Daily scheduler retries sync, logs failure, does not crash

### Stripe Payment Failed
**Test:** Mock Stripe webhook `invoice.payment_failed`.
**Expected behavior:**
- `tenant.subscription_status` → `past_due`
- Service continues for 14-day grace period (Stripe's smart retry handles retries)
- Slack notification: "⚠️ Payment failed. Update at {Stripe Customer Portal URL}"
- After 14 days `past_due` → `cancelled` via Stripe webhook
- On cancellation: final Slack message "Your subscription has ended. Data preserved for 30 days."
- Agent runs stop, but data remains in DB

### Slack Bot Removed
**Test:** Mock Slack API returning `channel_not_found` or `not_in_channel`.
**Expected behavior:**
- Agent completes analysis, saves to `agent_runs` with `output_result`
- Slack delivery marked as failed in `slack_messages`
- No crash, no retry loop
- When Slack reconnected: last 3 pending reports delivered

### Claude API Down
**Test:** Mock Anthropic API timeout.
**Expected behavior:**
- Retry once after 5 seconds
- If retry fails: return tool results only (numbers without narrative)
- Slack message: "📊 Here are your numbers. AI analysis temporarily unavailable."
- Log to `agent_runs` with `status: "completed_partial"`

### Database Connection Lost
**Test:** Mock asyncpg connection refused.
**Expected behavior:**
- Health endpoint returns 503
- All API routes return 503 with "Service temporarily unavailable"
- Slack bot responds: "I'm having trouble right now. Try again in a few minutes."
- No data corruption risk (read-only operations fail safely)

## CI/CD Pipeline — GitHub Actions

Set up in **Week 1**. Simple, fast, protective.

### `.github/workflows/ci.yml`

```yaml
name: CI

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main]

jobs:
  backend-checks:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v4
        with:
          version: "latest"

      - name: Install dependencies
        run: uv sync

      - name: Lint
        run: uv run ruff check .

      - name: Type check
        run: uv run mypy backend/ --ignore-missing-imports

      - name: Run tool tests
        run: uv run pytest tests/test_tools/ -v --tb=short

      - name: Run API tests
        run: uv run pytest tests/test_api/ -v --tb=short

      - name: Coverage report
        run: uv run pytest --cov=backend/app/tools --cov-report=term-missing

  frontend-checks:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: 20

      - name: Install dependencies
        working-directory: frontend
        run: npm ci

      - name: Lint
        working-directory: frontend
        run: npm run lint

      - name: Build
        working-directory: frontend
        run: npm run build
```

### `.github/workflows/deploy.yml`

```yaml
name: Deploy

on:
  workflow_dispatch:  # Manual trigger only — not on every push
    inputs:
      environment:
        description: 'Deploy to'
        required: true
        default: 'staging'
        type: choice
        options:
          - staging
          - production

jobs:
  deploy-backend:
    runs-on: ubuntu-latest
    if: github.ref == 'refs/heads/main'
    steps:
      - uses: actions/checkout@v4
      # Railway deploy via CLI or webhook
      - name: Deploy to Railway
        run: |
          curl -X POST "${{ secrets.RAILWAY_DEPLOY_WEBHOOK_URL }}"

  deploy-frontend:
    runs-on: ubuntu-latest
    if: github.ref == 'refs/heads/main'
    # Vercel auto-deploys on push to main — no action needed
    # This job exists only for visibility in the workflow
    steps:
      - run: echo "Frontend auto-deploys via Vercel Git integration"
```

**Branching strategy:**
- `main` — production. Deploy manually via `workflow_dispatch`.
- `develop` — working branch. CI runs on every push.
- Feature branches → PR to `develop` → CI must pass → merge.
- Solo founder shortcut: work directly on `develop`, PR to `main` for deploys.

**Weekly deploy cadence:** End of each sprint week, merge `develop` → `main`, trigger deploy. This creates a natural Agile sprint rhythm.

## Sprint Reporting

At the end of each sprint week, generate a report. Claude Code CLI can produce this.

### Template: SPRINT_REPORT.md

```markdown
# Sprint Report — Week {N}

**Date:** {date}
**Sprint Goal:** {goal from sprint plan}

## Status: {ON_TRACK | AT_RISK | BLOCKED}

## Completed
- [ ] Task 1 — description
- [ ] Task 2 — description

## In Progress
- [ ] Task 3 — {percentage}% complete, blocker: {if any}

## Not Started
- [ ] Task 4 — reason: {dependency / time}

## Test Coverage
| Module | Uncovered Lines | Status |
|--------|----------------|--------|
| tools/ | {list or "none"} | ✅ or ❌ |
| api/   | {list or "none"} | ✅ or ❌ |
| agent/ | {list or "none"} | ✅ or ❌ |

## CI Status
- Last CI run: {pass/fail}
- Failing checks: {list or "none"}

## Metrics
- Lines of code added: {N}
- Tests added: {N}
- API endpoints: {N} total
- Tools implemented: {N}/7
- Deploy: {yes/no, environment}

## Blockers
- {Blocker description + mitigation plan}

## Next Week Plan
- Priority 1: {task}
- Priority 2: {task}
- Priority 3: {task}

## Decisions Made
- {Any architectural or product decisions this week}
```

### How to Generate

Ask Claude Code CLI at the end of each week:

```
Review the codebase. Generate a sprint report for Week {N}.
Include: completed tasks, test coverage (run pytest --cov),
lines changed (git diff --stat), CI status, blockers, and
plan for next week. Save as docs/sprints/SPRINT_W{N}.md
```
