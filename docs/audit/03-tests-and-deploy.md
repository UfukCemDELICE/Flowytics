# Audit Report: Tests & Deployment Readiness

**Date:** 2026-03-28
**Auditor:** Claude Opus 4.6 (automated)
**Scope:** All backend Python modules, test coverage, CI/CD pipelines, deployment configuration

---

## SECTION F: Test Coverage Matrix

| Module | File | Has Tests? | Test File(s) | Test Quality | Risk if Untested |
|--------|------|-----------|-------------|-------------|-----------------|
| **tools/burn_rate** | `backend/app/tools/burn_rate.py` | Yes | `test_tools.py`, `test_edge_cases.py`, `test_edge_cases_sprint7.py` | **Thorough** — happy path, empty, zero-revenue, single-month, all-zeros, negative cash, profitable, trend assertions | Low |
| **tools/runway** | `backend/app/tools/runway.py` | Yes | `test_tools.py`, `test_edge_cases.py`, `test_edge_cases_sprint7.py` | **Thorough** — healthy/dying/profitable/critical/warning/monitor thresholds, empty, infinite, negative cash, boundary statuses | Low |
| **tools/cash_forecast** | `backend/app/tools/cash_forecast.py` | Yes | `test_tools.py`, `test_edge_cases.py`, `test_edge_cases_sprint7.py` | **Thorough** — happy path, dying (zero_cash_week), empty, zero-revenue, single-month, negative start, all-zeros | Low |
| **tools/anomaly** | `backend/app/tools/anomaly.py` | Yes | `test_advanced_tools.py`, `test_missing_coverage.py`, `test_edge_cases_sprint7.py` | **Thorough** — critical severity, warning severity, flat no-spike, flat then spike, insufficient history, empty, single-month | Low |
| **tools/fundraising** | `backend/app/tools/fundraising.py` | Yes | `test_advanced_tools.py`, `test_missing_coverage.py`, `test_edge_cases_sprint7.py` | **Thorough** — healthy, pre-revenue, empty financials, high growth rate, single-month, all-zeros, negative cash | Low |
| **tools/scenario** | `backend/app/tools/scenario.py` | Yes | `test_advanced_tools.py`, `test_edge_cases_sprint7.py` | **Adequate** — hire, cut_expense, infinite runway, empty, zero-revenue. Missing: multiple simultaneous changes, revenue_change edge cases | Low |
| **tools/financial_summary** | `backend/app/tools/financial_summary.py` | Yes | `test_edge_cases.py`, `test_edge_cases_sprint7.py` | **Thorough** — parsing, empty data, missing fields, null values, missing month field, null cash, completely empty dicts | Low |
| **tools/monthly_report** | `backend/app/tools/monthly_report.py` | Yes | `test_missing_coverage.py` | **Weak** — single test verifying output has expected fields. No edge cases, no empty-data path, no error cases | Medium |
| **tools/schemas** | `backend/app/tools/schemas.py` | Yes | Used extensively in fixtures across all tool tests | **Adequate** — validated indirectly through all tool tests | Low |
| **api/v1/me** | `backend/app/api/v1/me.py` | Yes | `test_api_auth.py` | **Adequate** — tests 401 without auth, 200 with auth. Missing: response shape validation beyond org_id | Medium |
| **api/v1/quickbooks** | `backend/app/api/v1/quickbooks.py` | Yes | `test_api_auth.py`, `test_qbo_error_handling.py`, `test_welcome_message.py` | **Adequate** — auth enforcement, OAuth redirect mock, background_first_sync, TokenExpiredError handling. Missing: callback success path with real token exchange, sync endpoint tests | High |
| **api/v1/stripe** | `backend/app/api/v1/stripe.py` | Yes | `test_graceful_degradation.py`, `test_security_audit.py`, `test_e2e_lifecycle.py` | **Adequate** — webhook degradation (payment_failed), checkout.session.completed, invalid signature handling. Missing: customer.subscription.deleted, invoice.paid | Medium |
| **api/v1/slack** | `backend/app/api/v1/slack.py` | Partial | `test_welcome_message.py`, `test_security_audit.py` | **Weak** — only auth enforcement (401) and _background_welcome_check tested. Missing: Slack event handler, install flow, event verification, message routing | **Critical** |
| **agent/graph** | `backend/app/agent/graph.py` | Yes | `test_agent/test_graph.py` | **Adequate** — should_continue routing (tools vs cross_validate). Missing: full graph invocation, error handling in graph nodes | Medium |
| **agent/select_model** | `backend/app/agent/select_model.py` | Yes | `test_agent/test_graph.py` | **Adequate** — Haiku/Sonnet/Opus routing tested. Missing: ambiguous inputs, very long messages | Low |
| **agent/cross_validate** | `backend/app/agent/cross_validate.py` | Yes | `test_agent/test_graph.py` | **Thorough** — clean pass, hallucination detection, year whitelisting, validation_edge routing | Low |
| **agent/state** | `backend/app/agent/state.py` | No | — | **None** | Low (data class) |
| **auth** | `backend/app/auth.py` | Partial | `test_api_auth.py` (mocked out) | **Weak** — auth dependency is overridden in tests, never tested with real JWT validation logic. The mock replaces the function entirely | **Critical** |
| **config** | `backend/app/config.py` | No | — | **None** | Medium |
| **database** | `backend/app/database.py` | No | — | **None** — always mocked in tests, real DB connection never tested | **Critical** |
| **logging_config** | `backend/app/logging_config.py` | Yes | `test_structured_logging.py` | **Thorough** — JSONFormatter, DevFormatter, correlation IDs, setup_logging, noisy logger quieting, exception info | Low |
| **middleware** | `backend/app/middleware.py` | Yes | `test_security_audit.py`, `test_structured_logging.py` | **Adequate** — security headers verified on responses, correlation ID generation/forwarding. Missing: edge cases for malformed headers | Low |
| **main** | `backend/app/main.py` | Partial | `test_health.py`, various TestClient tests | **Weak** — health endpoint tested, app starts. Scheduler jobs and lifespan not tested | Medium |
| **models/tenant** | `backend/app/models/tenant.py` | Yes | `test_models.py` | **Adequate** — defaults, TenantCreate validation, TenantRead field exclusion (stripe IDs) | Low |
| **models/integration** | `backend/app/models/integration.py` | Yes | `test_models.py` | **Adequate** — defaults, IntegrationRead credential exclusion | Low |
| **models/financial_snapshot** | `backend/app/models/financial_snapshot.py` | Yes | `test_models.py` | **Weak** — only tests dict acceptance for raw_data JSONB field | Low |
| **models/agent_run** | `backend/app/models/agent_run.py` | Yes | `test_models.py` | **Adequate** — Decimal cost, defaults (status, tokens, tools_called) | Low |
| **models/slack_message** | `backend/app/models/slack_message.py` | Yes | `test_models.py` | **Adequate** — minimal field tests, SlackUserMap | Low |
| **models/computed_metric** | `backend/app/models/computed_metric.py` | No | — | **None** | Low (data model) |
| **integrations/quickbooks** | `backend/app/integrations/quickbooks.py` | Yes | `test_qbo_error_handling.py`, `test_e2e_lifecycle.py`, `test_security_audit.py` | **Adequate** — handle_callback, auto_refresh_token (missing creds, refresh failure), TokenExpiredError hierarchy, Fernet roundtrip. Missing: actual QBO API report fetching logic | High |
| **integrations/slack** | `backend/app/integrations/slack.py` | Yes | `test_slack.py`, `test_slack_formatting.py` | **Thorough** — Block Kit formatting (CFO response, proactive alert, monthly report, error, stale data warning), currency/percent formatters, section splitter, None handling | Low |
| **integrations/stripe** | `backend/app/integrations/stripe.py` | No | — | **None** — verify_webhook is mocked everywhere, actual Stripe SDK calls never tested | High |
| **services/proactive_alerts** | `backend/app/services/proactive_alerts.py` | Partial | `test_graceful_degradation.py`, `test_slack.py` (import only) | **Weak** — only tests graceful no-data path and import. Missing: actual alert generation logic, threshold triggering, Slack delivery | **Critical** |
| **services/monthly_report** | `backend/app/services/monthly_report.py` | No | — | **None** — scheduled cron job with no tests | **Critical** |
| **services/onboarding_welcome** | `backend/app/services/onboarding_welcome.py` | Yes | `test_welcome_message.py` | **Thorough** — idempotency, milestone gating (no tenant, already complete, no Slack, no QBO sync), happy path, delivery failure retry, channel fallback, Block Kit quality, trigger integration | Low |
| **services/slack_agent_runner** | `backend/app/services/slack_agent_runner.py` | Yes | `test_e2e_lifecycle.py`, `test_qbo_error_handling.py`, `test_slack.py` (import) | **Adequate** — _check_qbo_data_freshness (no integration, disconnected, never synced, stale, fresh), process_slack_message via E2E. Missing: error paths in process_slack_message, agent timeout handling | Medium |
| **services/sync** | `backend/app/services/sync.py` | Partial | `test_e2e_lifecycle.py` | **Weak** — only tested via E2E with mocked QBO API. No unit tests for sync_tenant logic, error handling, partial sync failures | **Critical** |
| **utils/__init__** | `backend/app/utils/__init__.py` | No | — | **None** | Low (likely empty) |

### Coverage Summary

| Category | Modules | Tested | Untested | Thorough | Adequate | Weak |
|----------|---------|--------|----------|----------|----------|------|
| Tools | 9 | 9 | 0 | 6 | 2 | 1 |
| API Routes | 4 | 4 | 0 | 0 | 3 | 1 |
| Agent | 4 | 3 | 1 | 1 | 2 | 0 |
| Models | 6 | 5 | 1 | 0 | 4 | 1 |
| Services | 5 | 4 | 1 | 1 | 1 | 2 |
| Integrations | 3 | 2 | 1 | 1 | 1 | 0 |
| Infrastructure | 5 | 2 | 3 | 1 | 1 | 0 |
| **Total** | **36** | **29** | **7** | **10** | **14** | **5** |

**Critical untested modules:** `database.py`, `auth.py` (real JWT logic), `services/monthly_report.py`, `services/sync.py` (unit tests), `integrations/stripe.py`

---

## SECTION G: Test Quality Deep Dive

### G1. Assertion Quality

**Strong assertions (examples):**
- Tool tests assert specific `Decimal` values, status enums, list lengths, and boundary conditions — not just "no error"
- `test_cross_validate_math_hallucination` asserts specific message content, type (`HumanMessage`), and the `system_validator` name attribute
- `test_welcome_sent_when_all_milestones_met` asserts `onboarding_completed` state change, `send_message` was awaited exactly once, and the channel + text content of the call
- `test_e2e_signup_connect_sync_slack_report` asserts DB row counts, field values, data_type sets, raw_data contents, idempotency, and Slack reply content
- Security tests assert specific header values (`nosniff`, `DENY`), not just header presence

**Weak assertions (concerns):**
- `test_proactive_alerts_no_data`: `assert True` — passes if no exception, but doesn't verify any behavior or state
- `test_all_models_importable_from_init`: Empty `pass` — comment says "no assertion needed" but doesn't even attempt the import
- Several import smoke tests (`test_slack_agent_runner_import`, `test_proactive_alerts_import`) only verify `callable()` — minimal value
- `test_health_check`: Only checks status code and response body — doesn't test middleware behavior

### G2. External Service Mocking

| Service | Mocking Approach | Quality |
|---------|-----------------|---------|
| **Clerk JWT** | `app.dependency_overrides[get_current_user]` returns dict | Adequate — but the REAL auth.py JWT validation logic is never tested |
| **QuickBooks API** | `patch("...get_auth_client")`, `patch("...get_profit_and_loss")` etc. | Good — mocks at integration boundary |
| **Stripe** | `patch("...verify_webhook", return_value=mock_event)` | Adequate — but webhook signature verification is entirely skipped |
| **Slack** | `patch("...SlackClient")` with mock `send_message` | Good — consistent pattern across tests |
| **Anthropic/Claude** | `mock_agent.ainvoke = AsyncMock(return_value=...)` | Good — no real LLM calls |
| **Database** | `AsyncMock` sessions, `InMemoryDB` in E2E | Good — consistent patterns, no real DB needed |
| **Fernet Encryption** | Sometimes mocked, sometimes real | Mixed — security tests use real Fernet, others mock it |

**Key concern:** Stripe webhook signature verification (`verify_webhook`) is mocked in every test. The actual `stripe.Webhook.construct_event()` call is never tested. A misconfigured webhook secret in production would go undetected.

### G3. Integration/E2E Tests

**Yes, there are integration and E2E tests:**

1. **`test_e2e_lifecycle.py`** — Comprehensive 6-phase lifecycle test:
   - Signup → QBO Connect → Data Sync → Slack Connect → Welcome → Slack CFO Query
   - Uses `InMemoryDB` (custom in-memory SQLAlchemy-like session) — creative but fragile
   - Also tests: token expired mid-flow, stale data warning path, HTTP-level health + Stripe webhook

2. **`test_graceful_degradation.py`** — Integration tests for failure paths:
   - Stripe webhook with unknown customer
   - Proactive alerts with missing QBO data

3. **`test_structured_logging.py`** — Tests middleware integration via `TestClient`

**Missing integration tests:**
- No tests for the full LangGraph agent graph execution (tool selection → execution → cross-validation → response)
- No tests for APScheduler job triggering
- No database integration tests (all use mocks/in-memory)

### G4. Skipped/Commented/Expected-Fail Tests

- **No `@pytest.mark.skip` decorators found** anywhere
- **No `xfail` markers** found
- **No commented-out tests** found
- `test_all_models_importable_from_init` has an empty `pass` body — effectively a no-op, not a real test

### G5. CI Execution Verification

From `.github/workflows/ci.yml`:

```yaml
- name: Run tool tests
  run: uv run pytest tests/test_tools/ -v --tb=short

- name: Run API tests
  run: uv run pytest tests/test_api/ -v --tb=short

- name: Coverage report
  run: uv run pytest --cov=backend/app/tools --cov-report=term-missing
```

**Tests that run in CI:** `test_tools/` and `test_api/` only.

**Tests that DO NOT run in CI:**
| Test Directory | Tests | Why It Matters |
|---------------|-------|---------------|
| `test_agent/` | 4 tests | Agent routing/validation logic untested in CI |
| `test_models/` | 12 tests | Model defaults and schema safety untested in CI |
| `test_services/` | ~30 tests | Welcome message, graceful degradation, Slack formatting, QBO error handling, structured logging — ALL skipped in CI |
| `test_e2e/` | 4 tests | Full lifecycle E2E tests never run in CI |
| `test_security/` | ~15 tests | Security headers, CORS, auth enforcement, encryption — ALL skipped in CI |

**This is a critical finding.** Roughly 60+ tests exist but are not executed by CI. Only ~12 tests (tools + API) actually gate merges. A regression in security headers, Slack formatting, welcome messages, or the agent graph would pass CI.

**Coverage report scope:** `--cov=backend/app/tools` — only measures tool coverage. API, agent, services, integrations, and models coverage is not tracked.

---

## SECTION H: Deployment Readiness

### H1. Backend Deployment (Railway)

**Dockerfile:** DOES NOT EXIST
**railway.toml / railway.json:** DOES NOT EXIST
**Procfile:** DOES NOT EXIST

Railway can auto-detect Python projects, but without explicit configuration:
- No guarantee `uv` is used (Railway may default to `pip`)
- No health check configuration
- No memory/CPU limits defined
- No start command specified — Railway must guess (likely `uvicorn` but with what args?)

**What's needed:**
```
Missing:
  - Dockerfile or railway.toml with build/start commands
  - Health check path configuration (/api/v1/health)
  - Python version pinning (3.12)
  - uv installation in build step
  - Environment variable validation on startup
```

### H2. Frontend Deployment (Vercel)

**vercel.json:** DOES NOT EXIST
**next.config.ts:** Empty (no custom config)

Vercel auto-detects Next.js and deploys correctly in most cases. However:
- No environment variable configuration in `vercel.json`
- No build output configuration
- No rewrites/redirects for API proxying
- Relies entirely on Vercel's auto-detection

**Acceptable for MVP** — Vercel's Next.js auto-detection is reliable. The deploy workflow correctly notes this: `"Frontend auto-deploys via Vercel Git integration"`.

### H3. Environment Variables

**Documented in `.env.example`:** Yes, comprehensive.

| Variable | In .env.example | Required for Production | Status |
|----------|:---------------:|:----------------------:|--------|
| `DATABASE_URL` | Yes | Yes | Documented |
| `FERNET_KEY` | Yes | Yes | Documented with generation command |
| `FRONTEND_URL` | Yes | Yes | Documented |
| `LOG_LEVEL` | Yes | No | Documented |
| `LOG_FORMAT` | Yes | No | Documented |
| `CLERK_SECRET_KEY` | Yes | Yes | Documented |
| `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY` | Yes | Yes | Documented |
| `ANTHROPIC_API_KEY` | Yes | Yes | Documented |
| `QB_CLIENT_ID` | Yes | Yes | Documented |
| `QB_CLIENT_SECRET` | Yes | Yes | Documented |
| `QB_REDIRECT_URI` | Yes | Yes | Documented — **but hardcoded to localhost** |
| `QB_ENVIRONMENT` | Yes | Yes | Documented — must change from `sandbox` to `production` |
| `STRIPE_SECRET_KEY` | Yes | Yes | Documented |
| `STRIPE_WEBHOOK_SECRET` | Yes | Yes | Documented |
| `SLACK_BOT_TOKEN` | Yes | Yes | Documented |
| `SLACK_SIGNING_SECRET` | Yes | Yes | Documented |
| `SLACK_APP_TOKEN` | Yes | Yes | Documented |
| `SLACK_CLIENT_ID` | Yes | Yes | Documented |
| `SLACK_CLIENT_SECRET` | Yes | Yes | Documented |
| `RAILWAY_DEPLOY_WEBHOOK_URL` | No | Yes (CI/CD) | **Missing** — referenced in deploy.yml as a secret but not documented |

**No startup validation exists.** If any critical env var is missing, the app will crash at runtime when that code path is first hit, not at startup. `pydantic-settings` will fail at import time if required fields have no default and no env var — this is good, but only if all fields are truly `required` in the Settings model.

### H4. Database Migration Strategy

**Alembic directory:** DOES NOT EXIST (per `find` results)
**Migration files:** None

From CLAUDE.md: *"No Alembic migrations until schema changes become frequent."*

**Current approach:** SQLModel models define the schema, but there is no mechanism to:
1. Create tables in a fresh database
2. Apply schema changes to an existing database
3. Roll back schema changes

**Risk:** If the database is empty (first deploy), there is no `CREATE TABLE` mechanism. SQLModel's `SQLModel.metadata.create_all()` is not called anywhere in the codebase (not in `main.py` lifespan, not in `database.py`). The app will crash with "relation does not exist" on first query.

### H5. Production Blockers

**CRITICAL — App will not start/function:**

| # | Blocker | Severity | Details |
|---|---------|----------|---------|
| 1 | **No Dockerfile or Railway config** | Critical | Railway has no instructions for building or starting the app. No `uv` setup, no start command, no health checks. |
| 2 | **No database table creation** | Critical | No Alembic, no `create_all()` call. Fresh database = immediate crash on first request. |
| 3 | **CI runs only ~12 of ~75+ tests** | Critical | 60+ tests (security, services, agent, models, E2E) are not gated by CI. Regressions in security headers, Slack formatting, welcome flow, and agent routing would merge undetected. |
| 4 | **`QB_REDIRECT_URI` hardcoded to localhost** | Critical | `.env.example` shows `http://localhost:8000/...`. Production needs the real Railway URL. No documentation on what to set. |

**HIGH — App starts but has significant gaps:**

| # | Issue | Severity | Details |
|---|-------|----------|---------|
| 5 | **Auth never tested with real JWTs** | High | `get_current_user` is always overridden in tests. A misconfigured Clerk secret or broken JWT parsing wouldn't be caught until production. |
| 6 | **Stripe webhook signature never verified in tests** | High | `verify_webhook` is mocked everywhere. Invalid webhook secret config would pass tests but fail in production. |
| 7 | **`services/monthly_report.py` has zero tests** | High | A scheduler-triggered monthly cron job with no test coverage — errors will surface in production at 9 AM on the 1st of the month. |
| 8 | **`services/sync.py` has no unit tests** | High | The data sync pipeline (QBO → DB) is only tested via E2E with mocked API responses. Parsing logic, error handling for partial failures, and snapshot deduplication are untested. |
| 9 | **Deploy workflow has no CI gate** | High | `deploy.yml` uses `workflow_dispatch` but does not require CI to pass first. A manual deploy can push broken code. |
| 10 | **No staging environment separation** | High | Deploy workflow accepts "staging" or "production" but both use the same `RAILWAY_DEPLOY_WEBHOOK_URL` secret. No evidence of separate staging infra. |

**MEDIUM — Operational concerns:**

| # | Issue | Severity | Details |
|---|-------|----------|---------|
| 11 | **No logging/monitoring in deploy** | Medium | No health check after deploy, no rollback mechanism, no Sentry/error tracking. |
| 12 | **Slack event handler poorly tested** | Medium | `api/v1/slack.py` handles incoming Slack events (app_mention, messages) but has minimal test coverage for the actual event flow. |
| 13 | **`integrations/stripe.py` has zero tests** | Medium | The Stripe client module itself (not the API route) is untested. |
| 14 | **Coverage report only tracks `tools/`** | Medium | CI coverage step: `--cov=backend/app/tools`. API, agent, and service coverage is invisible. |
| 15 | **Frontend has no tests** | Medium | No test runner configured, no vitest/jest setup. CLAUDE.md mentions adding in "Week 6" — still missing. |

---

## Appendix: Test File Inventory

| Test File | # Tests (approx) | Runs in CI? |
|-----------|:-----------------:|:-----------:|
| `test_tools/test_tools.py` | 7 | Yes |
| `test_tools/test_advanced_tools.py` | 11 | Yes |
| `test_tools/test_edge_cases.py` | 4 | Yes |
| `test_tools/test_missing_coverage.py` | 4 | Yes |
| `test_tools/test_edge_cases_sprint7.py` | 27 | Yes |
| `test_api/test_health.py` | 1 | Yes |
| `test_api/test_api_auth.py` | 4 | Yes |
| `test_agent/test_graph.py` | 4 | **No** |
| `test_models/test_models.py` | 12 | **No** |
| `test_services/test_graceful_degradation.py` | 2 | **No** |
| `test_services/test_welcome_message.py` | 11 | **No** |
| `test_services/test_structured_logging.py` | 11 | **No** |
| `test_services/test_slack_formatting.py` | 20 | **No** |
| `test_services/test_slack.py` | 3 | **No** |
| `test_services/test_qbo_error_handling.py` | 9 | **No** |
| `test_e2e/test_e2e_lifecycle.py` | 4 | **No** |
| `test_security/test_security_audit.py` | 13 | **No** |
| **Total** | **~147** | **~53 (36%)** |

**64% of tests are invisible to CI.**
