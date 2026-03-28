# Audit Report 04 — Synthesis & Recommendations

**Date:** 2026-03-28
**Scope:** Final synthesis of reports 01 (Structure & Docs), 02 (Backend Quality), 03 (Tests & Deploy)
**Auditor:** Claude Opus 4.6

---

## SECTION I: Top 10 Risks

| # | Risk | Severity | What Breaks | Fix | Effort |
|---|------|----------|------------|-----|--------|
| 1 | **QBO JSON parser is a stub** — `parse_qbo_to_financial_summary` reads `pl_data["monthly_data"]` which doesn't exist in real QBO responses. `pl_rows` is fetched but never used. | Critical | Every financial tool returns zeros in production. Burn rate, runway, anomalies, alerts, monthly reports — all empty. The entire product is inert against real data. | Rewrite `financial_summary.py` to parse real QBO `ProfitAndLoss` JSON (`Rows.Row[]` nested structure). Add integration test with a real QBO sandbox response fixture. | 8h |
| 2 | **Financial data never loaded into agent** — `slack_agent_runner.py` invokes the graph with `{"messages": [...]}` only. `AgentState.financial_summary` is declared but never populated. Tools expect `FinancialSummary` as input but no code path provides it. | Critical | Agent cannot answer any financial question. Every Slack query that touches financial tools will fail or hallucinate. The Slack bot is non-functional for its core purpose. | Add a `load_financial_data` step in `slack_agent_runner.py` (or as a graph node) that fetches latest snapshots, parses via `parse_qbo_to_financial_summary`, and populates `AgentState.financial_summary`. | 4h |
| 3 | **All LLM model IDs are invalid** — `"claude-4-6-opus-latest"`, `"claude-4-5-haiku-latest"`, `"claude-4-6-sonnet-latest"` in `select_model.py`, `graph.py`, and `monthly_report.py`. | Critical | Every LLM call raises an API error. Agent responses, model routing, monthly report generation — all fail at runtime. | Replace with correct IDs: `claude-opus-4-6-20250514`, `claude-sonnet-4-5-20250514`, `claude-haiku-4-5-20251001`. Grep for all occurrences across the codebase. | 0.5h |
| 4 | **No database table creation mechanism** — No Alembic, no `create_all()` call anywhere. Fresh database = immediate crash. | Critical | First deploy to a new environment fails on the first DB query with "relation does not exist". Cannot onboard users, sync data, or run agent. | Add `SQLModel.metadata.create_all(engine)` in `main.py` lifespan startup (or a standalone init script). Document this as the pre-migration approach. | 1h |
| 5 | **No Dockerfile or Railway config** — No build/start instructions for Railway. | Critical | Backend cannot be deployed. Railway may guess wrong (pip instead of uv, wrong start command, no health checks). | Create a `Dockerfile` with Python 3.12, uv install, `uv sync`, and `uvicorn backend.app.main:app` start command. Add health check on `/api/v1/health`. | 2h |
| 6 | **64% of tests invisible to CI** — Only `test_tools/` and `test_api/` run. Security, services, agent, models, E2E tests (~94 tests) are skipped. | High | Regressions in security headers, Slack formatting, welcome flow, agent routing, model validation all merge undetected. Security audit tests exist but don't gate deployments. | Update `ci.yml` to run `uv run pytest backend/tests/ -v --tb=short` (all test directories). Expand coverage to `--cov=backend/app`. | 1h |
| 7 | **Authorization bypass on `trigger_monthly_report`** — Endpoint accepts `tenant_id` as query param without verifying the caller belongs to that tenant. | High | Any authenticated user can trigger monthly reports for any tenant. Data exposure across tenants. | Add `if tenant_id != user["org_id"]: raise HTTPException(403)` check. | 0.5h |
| 8 | **Cross-validation infinite loop** — No max retry count on the correction loop in `cross_validate.py`. | High | Computed percentages or reformatted numbers trigger false hallucination flags → infinite loop → Slack never gets a response → resource exhaustion. | Add `max_retries = 3` counter in the validation loop. After max retries, return the response with a disclaimer. | 1h |
| 9 | **Deploy workflow has no CI gate and staging/production are indistinguishable** — `environment` input is accepted but never used. Same webhook fires for both. | High | Broken code can be deployed manually. No staging environment to catch issues before production. A bad deploy has no rollback. | Wire `environment` input to separate Railway webhook URLs (staging vs prod). Add `needs: [test]` to require CI pass. Add `-f` flag to curl. | 2h |
| 10 | **`trigger_type="scheduled_report"` violates DB CHECK constraint** — `monthly_report.py` uses a value not in the allowed set (`scheduled`, `slack_message`, `webhook`, `manual`). | Medium | Monthly report scheduler crashes with a DB constraint violation on the first of every month. Reports never get logged. | Change to `trigger_type="scheduled"` or add `"scheduled_report"` to the CHECK constraint. | 0.25h |

---

## SECTION J: All Inconsistencies Found

### Code vs Documentation

| # | Inconsistency | Source A | Source B | Impact |
|---|--------------|----------|----------|--------|
| J1 | `backend/app/api/v1/` directory documented but doesn't exist — routes are registered directly via `main.py` without the v1 subdirectory structure | CLAUDE.md, backend.md | File tree | Confusing for new contributors |
| J2 | `backend/app/prompts/` directory documented with 5 .txt files — directory doesn't exist on disk | backend.md, agents.md | File tree | Prompts exist somewhere (system_base.txt etc. are referenced and appear to work) but not at the documented path |
| J3 | `models/slack_user_map.py` defined in db.md schema — no model file exists | db.md | File tree | Table may exist in DB but has no ORM model for queries |
| J4 | `financial_summary.py` is an 8th tool not in agents.md's 7-tool spec | agents.md (7 tools) | File tree (9 files in tools/) | Undocumented tool in the pipeline |
| J5 | Frontend onboarding pages marked [x] complete in sprint-plan — files don't exist in file tree | sprint-plan.md (Week 6) | File tree | Sprint tracking is inaccurate |
| J6 | architecture.md C4 diagram mentions "Xero" — CLAUDE.md explicitly says "No Xero support" | architecture.md | CLAUDE.md | Documentation contradiction |
| J7 | testing.md documents per-tool test files (test_burn_rate.py, test_runway.py...) — tests are consolidated in `test_tools.py` and `test_advanced_tools.py` | testing.md | File tree | Test structure doesn't match docs |
| J8 | Sprint-plan uses `QB_*` prefix for env vars — CLAUDE.md and config.py use `QBO_*` | sprint-plan.md | CLAUDE.md, config.py | New contributor may set wrong env vars |
| J9 | Sprint-plan references `docs/09-mimari-ve-gelistirme-seans-raporu.md` — file doesn't exist | sprint-plan.md | File tree | Dead reference |
| J10 | CLAUDE.md documentation map lists 6 files — 8+ doc files actually exist (sprint-plan.md, package-changes.md missing from map) | CLAUDE.md | File tree | Incomplete documentation index |
| J11 | `vitest` or `jest` to be added in Week 6 per testing.md — Week 6 marked complete but no test runner installed | testing.md, sprint-plan.md | package.json | Frontend has zero test coverage with no way to run tests |
| J12 | mypy claimed to run in "strict mode" per backend.md — CI runs with `--ignore-missing-imports` | backend.md | ci.yml | Type checking is less rigorous than documented |

### Code vs Code

| # | Inconsistency | File A | File B | Impact |
|---|--------------|--------|--------|--------|
| J13 | Proactive alert thresholds in prompt (`cash < 2x burn`, `runway < 6mo`) differ from hardcoded thresholds in service (`runway < 4mo`, `burn spike > 25%`) | system_base.txt | proactive_alerts.py | LLM may describe different thresholds than the scheduler actually uses |
| J14 | `config.py` still has `CODAT_API_KEY` and `CODAT_BASE_URL` — Codat was dropped | config.py | CLAUDE.md ("Codat dropped") | Dead config, confusing |
| J15 | Model comments in `integration.py` and `financial_snapshot.py` say `# CHECK: codat, plaid` — should be `quickbooks, plaid` | models/integration.py, models/financial_snapshot.py | CLAUDE.md | Misleading comments |
| J16 | `monthly_report.py` passes `runway` kwarg to `calculate_cash_forecast` — tool only accepts `summary` | monthly_report.py | cash_forecast.py | Extra kwarg silently ignored (no runtime error, but unexpected) |
| J17 | `get_qbo_client` queries by `realm_id` without `tenant_id` filter | quickbooks.py | CLAUDE.md rule 6 | Violates "every query filters by tenant_id" rule |
| J18 | `trigger_type="scheduled_report"` not in AgentRun CHECK constraint values | monthly_report.py | models/agent_run.py | DB constraint violation at runtime |
| J19 | Slack app uses `"xoxb-dummy-token"` and `"dummy-secret"` as fallbacks | integrations/slack.py | Security best practices | Dummy signing secret would accept forged requests if real values not set |

### Config vs Code

| # | Inconsistency | Config | Code | Impact |
|---|--------------|--------|------|--------|
| J20 | `.env.example` is gitignored — safe template won't be tracked | .gitignore | .env.example | New contributors won't see the env template |
| J21 | `RAILWAY_DEPLOY_WEBHOOK_URL` used in deploy.yml but not documented | deploy.yml | CLAUDE.md env var list | Ops gap during first deploy setup |
| J22 | `NEXT_PUBLIC_API_URL` referenced in frontend.md code sample but not in env var list | frontend.md | CLAUDE.md env var list | Frontend API calls may fail without this var |
| J23 | `.env.example` has `QB_REDIRECT_URI=http://localhost:8000/...` hardcoded | .env.example | Production needs | Production QBO OAuth will redirect to localhost |

---

## SECTION K: Top 15 Recommended Actions

### 1. Fix the QBO JSON parser (Risk I-1)
- **What:** Rewrite `backend/app/tools/financial_summary.py` → `parse_qbo_to_financial_summary` to parse the real QBO `ProfitAndLoss` response format (`Rows.Row[]` nested structure with `Header`, `ColData`, `Summary` nodes). Add a fixture file with a real QBO sandbox response.
- **Why:** Without this, every downstream tool returns zeros. The entire product is non-functional against real data. This is the single highest-impact fix.
- **Effort:** 8 hours
- **Dependencies:** Need a real QBO sandbox P&L response (can be captured from the existing sandbox connection).

### 2. Wire financial data into the agent graph (Risk I-2)
- **What:** In `backend/app/services/slack_agent_runner.py`, before invoking the graph: (a) fetch the tenant's latest `financial_snapshots` from DB, (b) call the fixed `parse_qbo_to_financial_summary`, (c) populate `AgentState.financial_summary`. Alternatively, add a `load_financial_data` node to the graph.
- **Why:** Agent currently has no financial context. Cannot answer any financial question.
- **Effort:** 4 hours
- **Dependencies:** Depends on #1 (parser fix).

### 3. Fix all LLM model IDs (Risk I-3)
- **What:** Search-and-replace across codebase: `"claude-4-6-opus-latest"` → `"claude-opus-4-6-20250514"`, `"claude-4-5-haiku-latest"` → `"claude-haiku-4-5-20251001"`, `"claude-4-6-sonnet-latest"` → `"claude-sonnet-4-5-20250514"`. Files: `agent/select_model.py`, `agent/graph.py`, `services/monthly_report.py`.
- **Why:** Every LLM call currently fails at runtime.
- **Effort:** 30 minutes
- **Dependencies:** None.

### 4. Create Dockerfile and Railway config (Risk I-5)
- **What:** Create `Dockerfile` with Python 3.12 base, install uv, `uv sync --frozen`, expose port, `CMD uvicorn backend.app.main:app --host 0.0.0.0 --port $PORT`. Add health check for `/api/v1/health`.
- **Why:** Cannot deploy without this.
- **Effort:** 2 hours
- **Dependencies:** None.

### 5. Add `create_all()` for database tables (Risk I-4)
- **What:** In `backend/app/main.py` lifespan, add `async with engine.begin() as conn: await conn.run_sync(SQLModel.metadata.create_all)`. This is idempotent (safe to run on existing tables).
- **Why:** Fresh database deploy crashes immediately.
- **Effort:** 1 hour
- **Dependencies:** None.

### 6. Run all tests in CI (Risk I-6)
- **What:** In `.github/workflows/ci.yml`, change test steps to `uv run pytest backend/tests/ -v --tb=short`. Change coverage to `--cov=backend/app --cov-report=term-missing`.
- **Why:** 94 tests (~64%) currently don't gate merges. Security, agent, and service regressions go undetected.
- **Effort:** 1 hour
- **Dependencies:** Verify all 147 tests pass locally first.

### 7. Fix the tenant authorization bypass (Risk I-7)
- **What:** In `backend/app/api/v1/slack.py`, `trigger_monthly_report` endpoint: add `if tenant_id != user["org_id"]: raise HTTPException(status_code=403, detail="Forbidden")`.
- **Why:** Cross-tenant data exposure. Any authenticated user can trigger reports for any tenant.
- **Effort:** 30 minutes
- **Dependencies:** None.

### 8. Add cross-validation retry limit (Risk I-8)
- **What:** In `backend/app/agent/cross_validate.py`, add a counter that tracks validation attempts. After 3 retries, return the response with a caveat instead of looping.
- **Why:** Infinite loop risk on computed percentages or formatted numbers.
- **Effort:** 1 hour
- **Dependencies:** None.

### 9. Fix deploy.yml (CI gate + staging separation + curl -f) (Risk I-9)
- **What:** (a) Add `needs: [test]` job dependency. (b) Use `environment` input to select between `RAILWAY_STAGING_WEBHOOK` and `RAILWAY_PROD_WEBHOOK` secrets. (c) Add `-f` flag to curl so HTTP errors are caught.
- **Why:** Broken code can be deployed to production. No staging safety net.
- **Effort:** 2 hours
- **Dependencies:** Need separate Railway staging project.

### 10. Fix `trigger_type` CHECK constraint violation (Risk I-10)
- **What:** In `backend/app/services/monthly_report.py`, change `trigger_type="scheduled_report"` to `trigger_type="scheduled"`.
- **Why:** Monthly report scheduler crashes with DB error on the 1st of every month.
- **Effort:** 15 minutes
- **Dependencies:** None.

### 11. Fix .gitignore (remove .env.example, add missing patterns)
- **What:** Remove `.env.example` from `.gitignore`. Add: `*.pem`, `*.key`, `*.sqlite`, `*.db`, `frontend/.clerk/.tmp/`, `*.tsbuildinfo`, `ruff_report.txt`, `LastSummary.md`, `LastWalkthrough.md`.
- **Why:** `.env.example` should be committed for onboarding. Build artifacts and secrets should be ignored.
- **Effort:** 30 minutes
- **Dependencies:** None.

### 12. Remove dead Codat references
- **What:** Remove `CODAT_API_KEY` and `CODAT_BASE_URL` from `config.py`. Fix model comments in `integration.py` and `financial_snapshot.py` from `# CHECK: codat, plaid` to `# CHECK: quickbooks, plaid`.
- **Why:** Misleading config and comments from a dropped integration.
- **Effort:** 15 minutes
- **Dependencies:** None.

### 13. Reconcile documentation with reality
- **What:** Update CLAUDE.md, backend.md, agents.md, testing.md to match the actual file tree. Key changes: (a) document `financial_summary.py` as the 8th tool, (b) update test file structure, (c) add sprint-plan.md to doc map, (d) remove references to non-existent `api/v1/` subdirectory structure, (e) clarify prompt file locations.
- **Why:** Documentation drift causes confusion and incorrect onboarding.
- **Effort:** 3 hours
- **Dependencies:** After fixes #1-#12 so docs reflect the fixed state.

### 14. Align proactive alert thresholds (prompt vs code)
- **What:** Make `system_base.txt` thresholds match `proactive_alerts.py` (or vice versa). Currently: prompt says `runway < 6 months`, code says `runway < 4 months`.
- **Why:** LLM will describe thresholds that don't match actual alert behavior.
- **Effort:** 30 minutes
- **Dependencies:** Product decision on which thresholds are correct.

### 15. Add missing `slack_user_map` model
- **What:** Create `backend/app/models/slack_user_map.py` with the SQLModel definition matching the schema in db.md. Register in `models/__init__.py`.
- **Why:** Table exists in DB but has no ORM model for queries. Slack user mapping won't work.
- **Effort:** 1 hour
- **Dependencies:** None.

---

## SECTION L: Sprint Health Summary

### Weeks 1-3: Verified Status (as of 2026-03-28)

| Week | Claimed | Verified | Actual Status |
|------|---------|----------|---------------|
| **Week 1** (Mar 9-15): Infrastructure & QBO | All items [x] | **Mostly verified** | FastAPI app starts, Clerk auth works, QBO OAuth flow complete, sync service persists snapshots. Router registration confirmed. **Gap:** `api/v1/` directory doesn't exist as a subdirectory — routes are mounted differently than documented. |
| **Week 2** (Mar 16-22): Financial Tools | All items [x] | **Partially verified** | `burn_rate`, `runway`, `cash_forecast`, `scenario` — all correctly implemented with Decimal discipline. **Critical gap:** `financial_summary.py` (the QBO parser) is a stub. It parses a test fixture format, not real QBO JSON. This means the tool "exists" and "passes tests" but doesn't work with real data. All tests use synthetic fixtures that match the stub's expected format. |
| **Week 3** (Mar 23-29): Anomaly & Scenario | All items [x] | **Partially verified** | `anomaly.py`, `scenario.py`, `fundraising.py` — all implemented. Agent graph skeleton works. Model routing logic exists but uses invalid model IDs (will fail at runtime). Cross-validation has no retry limit. Prompt files exist (location unclear vs docs). **Missing spec items:** anomaly detection doesn't cover new/disappeared categories or vendor concentration. |

**Bottom line for Weeks 1-3:** The code structure is there. Tools calculate correctly on synthetic data. But two critical bugs (QBO parser stub + agent data flow) mean the system is non-functional against real QuickBooks data. Tests pass because they use synthetic fixtures that match the stub, masking the real problem.

### Week 4: What's Ready to Start, What's Blocked

**Week 4 (Mar 30 – Apr 5): Slack Bot & Proactive Alerts**

Sprint-plan marks all Week 4 items as [x] complete. Audit confirms:

| Ready | Blocked |
|-------|---------|
| Slack Bolt mounted to FastAPI ✅ | Slack bot cannot answer financial questions (agent has no data — Risk I-2) |
| Block Kit formatting is thorough ✅ | Proactive alerts will return no alerts (QBO parser stub — Risk I-1) |
| APScheduler configured for daily checks ✅ | Model IDs invalid — all LLM calls fail (Risk I-3) |
| 3-second Slack acknowledge works ✅ | `trigger_monthly_report` has auth bypass (Risk I-7) |
| Message logging to `slack_messages` ✅ | |

**Verdict:** Week 4 code exists but is non-functional until Risks I-1, I-2, and I-3 are fixed. Those three fixes together (~12.5h) would unblock Weeks 4-5 entirely.

### Weeks 5-8: Architectural Gaps That Will Slow These Down

| Week | Key Deliverable | Blocking Gap |
|------|----------------|-------------|
| **Week 5** (Apr 6-12): Monthly CFO Report | `services/monthly_report.py` has zero tests, uses invalid model ID, `trigger_type` violates DB constraint. Needs QBO parser fix (#1) + model ID fix (#3) + constraint fix (#10). **Also blocked by:** no DB table creation (#5) if deploying fresh. |
| **Week 6** (Apr 13-19): Onboarding & Stripe | Frontend onboarding pages are marked complete but **don't exist** in the file tree. Either they were built and removed, or the sprint tracker is wrong. This is a full re-implementation. Stripe webhook handler partially tested but `verify_webhook` is never tested with real signatures. No frontend test runner. **Estimated real effort:** 2-3 days for onboarding UI if starting from scratch. |
| **Week 7** (Apr 20-26): Polish & Demo | No Dockerfile (can't deploy), no staging environment, deploy.yml is broken. Demo requires a working deployed product. Landing page and Loom video are non-technical tasks. Security audit tests exist but don't run in CI. |
| **Week 8** (Apr 27 – May 3): Launch | Requires everything above to work. Real QBO connection with real data, working Slack bot, deployed to Railway, onboarding flow functional. |

### Overall: Is the June Deadline Realistic?

The sprint-plan targets **May 3** (not June) as the 8-week deadline. Today is March 28 — that's **5 weeks remaining**.

**Honest assessment:**

The codebase has substantial scaffolding. Auth, OAuth, Slack formatting, tool math, and the agent graph structure are solid. But three critical runtime bugs (QBO parser, agent data flow, model IDs) mean the core product loop is broken. Fixing these is ~12.5 hours of focused work.

**What's actually needed to ship by May 3:**

| Task | Effort | Week |
|------|--------|------|
| Fix QBO parser, agent data flow, model IDs (#1-3) | 12.5h | Week 4 (now) |
| Dockerfile + create_all + deploy.yml (#4-5, #9) | 5h | Week 4 (now) |
| Quick fixes: auth bypass, retry limit, trigger_type, .gitignore (#7-8, #10-11) | 3h | Week 4 (now) |
| Run all tests in CI (#6) | 1h | Week 4 (now) |
| Monthly report fixes + tests (Week 5 deliverable) | 4h | Week 5 |
| Frontend onboarding (if truly missing) | 16-24h | Week 5-6 |
| Staging environment + deploy pipeline | 4h | Week 6 |
| Polish, demo video, landing page | 8h | Week 7 |
| Outreach + first customers | — | Week 8 |

**Total engineering work remaining:** ~55-65 hours

**Verdict:** The May 3 deadline is **tight but possible** for a solo founder IF:
1. The three critical runtime bugs are fixed this week (Week 4)
2. The frontend onboarding situation is clarified — if it truly needs to be rebuilt from scratch, that's the biggest risk to timeline
3. Scope discipline is maintained — no new features, only fix-and-ship
4. "Launch" means "3 demos with real QBO data," not "production-hardened SaaS"

**Biggest risk to timeline:** The frontend onboarding. If those pages were never built (despite being marked complete), that's 2-3 days of UI work that isn't budgeted. Clarify this immediately.

---

*This synthesis consolidates findings from audit reports [01-structure-and-docs.md](docs/audit/01-structure-and-docs.md), [02-backend-quality.md](docs/audit/02-backend-quality.md), and [03-tests-and-deploy.md](docs/audit/03-tests-and-deploy.md). Generated 2026-03-28.*
