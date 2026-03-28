# Audit Report 01 — Structure & Documentation

**Date:** 2026-03-28
**Scope:** Project structure, documentation, config files, CI/CD. No backend source code or test code read.
**Auditor:** Claude Opus 4.6

---

## SECTION A: Project Structure & Organization

### A1. Directory Structure

**Overall:** The structure is logically organized and matches the monorepo pattern described in CLAUDE.md. However, there are significant gaps between what's documented and what exists.

#### Missing Directories/Files (Documented but don't exist)

| Documented Location | Referenced In | Status |
|---|---|---|
| `backend/app/api/v1/` | CLAUDE.md, backend.md | **MISSING** — only `backend/app/api/__init__.py` exists. No v1 directory, no route files (health.py, etc.) |
| `backend/app/prompts/` | CLAUDE.md, backend.md, agents.md | **MISSING** — entire directory absent. 5 prompt .txt files documented but none exist |
| `backend/app/models/slack_user_map.py` | db.md (schema defined) | **MISSING** — 6 of 7 model files exist, this one is absent |
| `frontend/src/app/sign-in/` | frontend.md | **MISSING** — Clerk sign-in page directory |
| `frontend/src/app/sign-up/` | frontend.md | **MISSING** — Clerk sign-up page directory |
| `frontend/src/app/onboarding/` | frontend.md (5 sub-pages) | **MISSING** — entire onboarding wizard absent |
| `frontend/src/app/settings/` | frontend.md | **MISSING** — settings page absent |
| `docs/sprints/` | testing.md | **MISSING** — sprint report directory referenced but never created |
| `alembic/` | CLAUDE.md | Expected absent (post-MVP) |

#### Undocumented Files (Exist but no doc mentions them)

| File | Likely Purpose | Concern Level |
|---|---|---|
| `backend/app/middleware.py` | Custom middleware | Medium — should be in backend.md |
| `backend/app/logging_config.py` | Structured logging | Low — sprint-plan mentions logging setup |
| `backend/app/tools/schemas.py` | Shared Pydantic schemas for tools | Medium — agents.md should reference |
| `backend/app/tools/financial_summary.py` | P&L/BS summary extraction | Medium — sprint-plan mentions it as a tool, agents.md doesn't |
| `backend/app/services/monthly_report.py` | Report orchestration service | Medium — duplication concern with `tools/monthly_report.py` |
| `backend/app/services/onboarding_welcome.py` | Welcome message logic | Low |
| `backend/app/services/proactive_alerts.py` | Alert threshold service | Low |
| `backend/app/services/slack_agent_runner.py` | Slack-to-agent bridge | Low |
| `docs/package-changes.md` | Package change log | Low — not in doc map |
| `docs/sprint-plan.md` | Sprint plan | Low — not in CLAUDE.md doc map |

#### Orphaned/Misplaced Files

| File | Issue |
|---|---|
| `backend/test_db.py` | Misplaced — should be in `backend/tests/` or deleted |
| `LastSummary.md` (root) | Orphan — not referenced anywhere, likely a session artifact |
| `LastWalkthrough.md` (root) | Orphan — same |
| `ruff_report.txt` (root) | Orphan — lint report artifact, should be in .gitignore or deleted |
| `frontend/.clerk/.tmp/` | Clerk temp files — should be gitignored |
| `frontend/tsconfig.tsbuildinfo` | Build artifact — should be gitignored |

#### Naming Inconsistencies

- `backend/app/models/computed_metric.py` (singular) vs `computed_metrics` (table name, plural). Other models use singular filenames matching the entity — this is consistent, not a problem.
- `backend/app/tools/financial_summary.py` — not in the 7-tool spec from agents.md but referenced in sprint-plan as `get_financial_summary`. This is an 8th tool that docs don't acknowledge.

---

### A2. pyproject.toml — Dependency Audit

**Python version:** `>=3.12` (matches CLAUDE.md)

#### Production Dependencies

| Package | Documented? | Used? | Notes |
|---|---|---|---|
| `aiohttp>=3.13.3` | No | Unclear | Not mentioned in any doc. Possibly a transitive dep pulled in as direct. **Flag.** |
| `anthropic>=0.83.0` | Yes | Yes | Claude API client |
| `apscheduler>=3.11.0` | Yes | Yes | Scheduler |
| `asyncpg>=0.31.0` | Yes | Yes | Postgres async driver |
| `clerk-backend-api>=5.0.2` | Yes | Yes | Clerk JWT verification |
| `cryptography>=46.0.5` | Yes | Yes | Credential encryption |
| `fastapi[standard]>=0.129.2` | Yes | Yes | Web framework |
| `httpx>=0.28.1` | No | Likely | HTTP client, probably for integration API calls. Not documented. |
| `intuit-oauth>=1.2.6` | Partially | Yes | QBO OAuth. Sprint-plan mentions it. |
| `langchain-anthropic>=1.3.3` | Implied | Yes | LangGraph + Claude bridge |
| `langchain-core>=1.2.14` | Implied | Yes | LangGraph dependency |
| `langgraph>=1.0.9` | Yes | Yes | Agent orchestration |
| `orjson>=3.11.7` | Yes | Yes | Fast JSON |
| `plaid-python>=29.0.0` | Yes | Premature | Plaid is "planned for later" — dep installed before needed (YAGNI violation) |
| `polars>=1.38.1` | Yes | Yes | Data processing |
| `pydantic-settings>=2.13.1` | Yes | Yes | Config management |
| `pyjwt>=2.11.0` | Yes | Yes | JWT decode |
| `python-dotenv>=1.2.1` | Implied | Yes | .env loading |
| `python-quickbooks>=0.9.12` | Yes | Yes | QBO API client |
| `slack-bolt>=1.27.0` | Yes | Yes | Slack bot framework |
| `slack-sdk>=3.40.1` | Yes | Yes | Slack API client |
| `sqlmodel>=0.0.37` | Yes | Yes | ORM |
| `stripe>=14.3.0` | Yes | Yes | Billing |
| `uvicorn[standard]>=0.41.0` | Yes | Yes | ASGI server |

**Findings:**
1. **`aiohttp`** — undocumented direct dependency. May be used by `intuit-oauth` or `python-quickbooks` transitively, but shouldn't be a direct dep unless explicitly used.
2. **`httpx`** — undocumented but likely used for HTTP calls to external APIs.
3. **`intuit-oauth` + `python-quickbooks`** — two QBO libraries. `python-quickbooks` likely uses `intuit-oauth` internally. Having both as direct deps may be intentional (OAuth flow vs API calls) but should be documented.
4. **`plaid-python`** — installed now but Plaid is explicitly "planned for later." Violates stated YAGNI principle.

#### Dev Dependencies

| Package | Purpose | Status |
|---|---|---|
| `mypy>=1.19.1` | Type checking | OK |
| `pytest>=9.0.2` | Testing | OK |
| `pytest-asyncio>=1.3.0` | Async test support | OK |
| `pytest-cov>=7.0.0` | Coverage reporting | OK |
| `ruff>=0.15.2` | Linting + formatting | OK |

**Missing dev dep:** No `pytest-mock` or `unittest.mock` wrapper — tests likely use stdlib mock, which is fine.

---

### A3. Frontend package.json — Dependency Audit

#### Production Dependencies

| Package | Documented? | Notes |
|---|---|---|
| `@clerk/nextjs ^6.38.1` | Yes | Auth |
| `@stripe/stripe-js ^8.8.0` | Yes | Client-side Stripe |
| `class-variance-authority ^0.7.1` | Implied | shadcn/ui dependency |
| `clsx ^2.1.1` | Implied | Utility for classnames |
| `lucide-react ^0.576.0` | Implied | Icon library for shadcn/ui |
| `next 16.1.6` | Yes | Framework |
| `radix-ui ^1.4.3` | Implied | shadcn/ui primitives |
| `react 19.2.3` | Yes | UI library |
| `react-dom 19.2.3` | Yes | React DOM |
| `stripe ^20.3.1` | Partially | **This is the server-side Stripe SDK.** In a Next.js project, used for server components/API routes. frontend.md mentions `@stripe/stripe-js` (client) but not `stripe` (server). |
| `tailwind-merge ^3.5.0` | Implied | shadcn/ui utility |

**Missing:**
| Package | Referenced In | Status |
|---|---|---|
| `react-plaid-link` | frontend.md | Not installed — Plaid is planned for later. Consistent with YAGNI. |
| `vitest` or `jest` | testing.md ("add in Week 6") | Not installed — currently Week 3 per sprint plan dates, but sprint plan shows Week 6 tasks completed. No test runner. |

**Unexpected:**
- `stripe` (server SDK) in frontend — likely used in Next.js server actions/route handlers for creating Checkout Sessions. Should be documented in frontend.md.

#### Dev Dependencies

All look appropriate for a Next.js + Tailwind + shadcn/ui project. `shadcn ^3.8.5` is the CLI tool for adding components.

---

### A4. CI/CD Completeness

#### ci.yml

| Step | Present? | Notes |
|---|---|---|
| Checkout | Yes | `actions/checkout@v4` |
| Setup uv | Yes | `astral-sh/setup-uv@v4` |
| Install deps | Yes | `uv sync` |
| Lint (ruff) | Yes | `uv run ruff check .` |
| Type check (mypy) | Yes | `uv run mypy backend/ --ignore-missing-imports` |
| Tool tests | Yes | `uv run pytest tests/test_tools/ -v --tb=short` |
| API tests | Yes | `uv run pytest tests/test_api/ -v --tb=short` |
| Coverage | Yes | Tools only |
| Frontend lint | Yes | `npm run lint` |
| Frontend build | Yes | `npm run build` |

**Missing from CI:**
1. **Python version not pinned** — no `python-version` input to `setup-uv`. Relies on `.python-version` file and uv's default behavior.
2. **Agent tests not run** — `backend/tests/test_agent/` exists but CI doesn't run it.
3. **Service tests not run** — `backend/tests/test_services/` (6 test files) not in CI.
4. **Security tests not run** — `backend/tests/test_security/` exists but not in CI.
5. **E2E tests not run** — `backend/tests/test_e2e/` exists but not in CI.
6. **Model tests not run** — `backend/tests/test_models/` exists but not in CI.
7. **Frontend tests missing** — no `npm run test` step (no test runner installed).
8. **No dependency caching** — both uv and npm could benefit from caching.
9. **No `ruff format --check`** — only linting, not format checking.
10. **Coverage only for tools** — API endpoint coverage not measured.

#### deploy.yml

| Aspect | Status | Notes |
|---|---|---|
| Manual trigger | Yes | `workflow_dispatch` |
| Environment input | Yes | staging/production choice |
| Main branch gate | Yes | `if: github.ref == 'refs/heads/main'` |
| Railway deploy | Yes | Via webhook URL |
| Vercel deploy | Placeholder | Just an echo — Vercel auto-deploys on push |

**Issues:**
1. **Environment input is unused** — the `environment` input (staging vs production) is accepted but never referenced in the job steps. Railway webhook fires the same regardless. **This is a bug** — staging vs production deploys are indistinguishable.
2. **No CI gate** — deploy.yml doesn't require CI to pass first. You can trigger a deploy without tests passing.
3. **No environment protection rules** — GitHub Environment protection (require reviewers, wait timer) not configured.
4. **No rollback mechanism** — no way to roll back a failed deploy.
5. **Secrets not validated** — `RAILWAY_DEPLOY_WEBHOOK_URL` failure would be silent (curl returns 0 even on HTTP errors without `-f`).

---

### A5. .gitignore Audit

**Current .gitignore:**
```
.env
.env.local
.env.*.local
.env.example        <-- PROBLEM
__pycache__/
*.py[cod]
*.egg-info/
dist/
.venv/
.mypy_cache/
.pytest_cache/
.ruff_cache/
.coverage
htmlcov/
node_modules/
.next/
.vercel/
.vscode/
.idea/
.DS_Store
Thumbs.db
*.log
```

**Critical Issues:**

| Issue | Severity | Detail |
|---|---|---|
| `.env.example` is gitignored | **HIGH** | `.env.example` is a safe credential template (no secrets) that SHOULD be committed. Sprint 7 created it, but gitignore prevents it from being tracked. New devs won't see it. |
| `.env` at root exists | **HIGH** | `.env` is gitignored (good) but exists in the working tree. Verify it's not committed with `git ls-files .env`. |
| `frontend/.env` exists | **MEDIUM** | Same concern. Should be gitignored (it matches `.env` pattern at root level of gitignore, but gitignore patterns are relative — need to verify this works for subdirectories). |

**Missing entries (should be added):**

| Pattern | Reason |
|---|---|
| `*.pem` / `*.key` | Certificate/key files |
| `*.sqlite` / `*.db` | Local database files |
| `frontend/.clerk/.tmp/` | Clerk temporary files (visible in tree) |
| `*.tsbuildinfo` | TypeScript build cache (`tsconfig.tsbuildinfo` exists) |
| `ruff_report.txt` | Lint report artifact |
| `LastSummary.md` / `LastWalkthrough.md` | Session artifacts |

**Note:** `frontend/.gitignore` likely exists separately (visible in tree) and may cover some of these.

---

## SECTION B: Documentation Completeness

### B1. CLAUDE.md

| Documented Claim | Exists in Tree? | Status |
|---|---|---|
| `backend/app/main.py` | Yes | OK |
| `backend/app/config.py` | Yes | OK |
| `backend/app/auth.py` | Yes | OK |
| `backend/app/database.py` | Yes | OK |
| `backend/app/api/v1/` (directory with routes) | No — only `api/__init__.py` | **MISSING** |
| `backend/app/agent/` | Yes (4 files) | OK |
| `backend/app/tools/` | Yes (9 files) | OK |
| `backend/app/integrations/` | Yes (3 files: quickbooks, slack, stripe) | OK |
| `backend/app/models/` | Yes (6 model files) | OK |
| `backend/app/services/` | Yes (5 service files) | OK |
| `backend/app/prompts/` | No | **MISSING** |
| `backend/tests/` | Yes (rich structure) | OK |
| `frontend/src/app/` | Yes (3 files only) | Partial |
| `frontend/src/components/` | Yes (4 components) | OK |
| `frontend/src/lib/` | Yes (2 files) | OK |
| `alembic/` | No (post-MVP, expected) | OK |
| `uv.lock` | Yes | OK |
| `utils/` mentioned in DRY section | Yes but empty (`__init__.py` only) | Unused |
| Plaid in integrations list | Not in `integrations/` directory | Not yet implemented |
| Documentation map: 6 doc files | 8 doc files exist (+ sprint-plan.md, package-changes.md) | Outdated |

### B2. docs/architecture.md

| Documented Claim | Exists in Tree? | Status |
|---|---|---|
| Single FastAPI process | Can't verify without source | N/A |
| Slack Bolt ASGI adapter | `integrations/slack.py` exists | OK |
| APScheduler | In pyproject.toml deps | OK |
| LangGraph agent | `agent/` directory exists | OK |
| QuickBooks API integration | `integrations/quickbooks.py` exists | OK |
| Plaid API (planned) | `plaid-python` in deps, no integration file | Premature dep |
| Stripe API | `integrations/stripe.py` exists | OK |
| Clerk API | `clerk-backend-api` in deps, `auth.py` exists | OK |
| Supabase PgBouncer | Can't verify without source | N/A |
| Mentions Xero in diagram | CLAUDE.md says "No Xero" | Inconsistent — architecture.md C4 diagram says "QBO, Xero" but Xero is explicitly out of scope |

### B3. docs/backend.md

| Documented Claim | Exists in Tree? | Status |
|---|---|---|
| `backend/app/database.py` | Yes | OK |
| `backend/app/config.py` | Yes | OK |
| `backend/app/models/tenant.py` | Yes | OK |
| `backend/app/api/v1/health.py` | No — no `api/v1/` directory | **MISSING** |
| `backend/app/prompts/` (5 .txt files) | No — directory doesn't exist | **MISSING** |
| `backend/app/prompts/slack_chat.txt` | No | **MISSING** |
| `backend/app/prompts/report_generation.txt` | No | **MISSING** |
| `backend/app/prompts/scenario_analysis.txt` | No | **MISSING** |
| `backend/app/prompts/anomaly_interpretation.txt` | No | **MISSING** |
| `backend/app/prompts/system_base.txt` | No | **MISSING** |
| Polars for data processing | `polars` in pyproject.toml | OK |
| orjson as default serializer | `orjson` in pyproject.toml | OK |
| ruff for linting + formatting | `ruff` in dev deps | OK |
| mypy strict mode | `mypy` in dev deps | OK (--ignore-missing-imports in CI suggests not full strict) |

### B4. docs/agents.md

| Documented Claim | Exists in Tree? | Status |
|---|---|---|
| `backend/app/tools/burn_rate.py` | Yes | OK |
| `backend/app/tools/runway.py` | Yes | OK |
| `backend/app/tools/cash_forecast.py` | Yes | OK |
| `backend/app/tools/anomaly.py` | Yes | OK |
| `backend/app/tools/scenario.py` | Yes | OK |
| `backend/app/tools/fundraising.py` | Yes | OK |
| `backend/app/tools/monthly_report.py` | Yes | OK |
| 7 tools total | 9 files in `tools/` (+ `schemas.py`, `financial_summary.py`, `__init__.py`) | Undocumented tools |
| `backend/app/prompts/` referenced | Directory doesn't exist | **MISSING** |
| Agent graph in `agent/` | `agent/graph.py`, `state.py`, `select_model.py`, `cross_validate.py` exist | OK |
| Cross-validation logic | `agent/cross_validate.py` exists | OK |
| Model routing | `agent/select_model.py` exists | OK |

**Undocumented tools:** `financial_summary.py` and `schemas.py` exist in `tools/` but are not mentioned in agents.md's 7-tool specification.

### B5. docs/db.md

| Documented Claim | Exists in Tree? | Status |
|---|---|---|
| `tenants` table / `models/tenant.py` | Yes | OK |
| `integrations` table / `models/integration.py` | Yes | OK |
| `financial_snapshots` table / `models/financial_snapshot.py` | Yes | OK |
| `computed_metrics` table / `models/computed_metric.py` | Yes | OK |
| `agent_runs` table / `models/agent_run.py` | Yes | OK |
| `slack_messages` table / `models/slack_message.py` | Yes | OK |
| `slack_user_map` table / model file | **No model file** | **MISSING** — schema in db.md, no `models/slack_user_map.py` |
| 7 tables total | 6 model files | 1 missing |

### B6. docs/frontend.md

| Documented Claim | Exists in Tree? | Status |
|---|---|---|
| `frontend/src/app/page.tsx` | Yes | OK |
| `frontend/src/app/layout.tsx` | Yes | OK |
| `frontend/src/app/globals.css` | Yes (not documented but exists) | OK |
| `frontend/src/app/sign-in/[[...sign-in]]/page.tsx` | No | **MISSING** |
| `frontend/src/app/sign-up/[[...sign-up]]/page.tsx` | No | **MISSING** |
| `frontend/src/app/onboarding/` (6 pages) | No | **MISSING** |
| `frontend/src/app/settings/page.tsx` | No | **MISSING** |
| `frontend/middleware.ts` | Yes at `frontend/src/middleware.ts` | OK (path slightly different) |
| `frontend/src/lib/api.ts` | Yes | OK |
| `@clerk/nextjs` | Yes in package.json | OK |
| `@stripe/stripe-js` | Yes in package.json | OK |
| `react-plaid-link` | No in package.json | Expected — Plaid planned for later |
| shadcn/ui components | `shadcn` CLI in devDeps, component files minimal | Partial |

**Assessment:** Frontend docs describe a complete 5-step onboarding wizard that doesn't exist yet. Only the root page, layout, a few utility components, and integration connect buttons are built. The sprint-plan says "Onboarding UI %90 tamamlandi" (90% complete) but the file tree contradicts this — the onboarding pages may have been built and then removed, or the sprint-plan is inaccurate.

### B7. docs/testing.md

| Documented Claim | Exists in Tree? | Status |
|---|---|---|
| `tests/test_tools/test_burn_rate.py` | No (tests consolidated in `test_tools.py`) | Structural divergence |
| `tests/test_tools/test_runway.py` | No (same) | Structural divergence |
| `tests/test_tools/test_cash_forecast.py` | No (same) | Structural divergence |
| `tests/test_tools/test_anomaly.py` | No (same) | Structural divergence |
| `tests/test_tools/test_scenario.py` | No (same) | Structural divergence |
| `tests/test_tools/test_fundraising.py` | No (same) | Structural divergence |
| `tests/test_tools/conftest.py` | Yes | OK |
| `tests/test_api/test_health.py` | Yes | OK |
| `tests/test_api/test_onboarding.py` | No | **MISSING** |
| `tests/test_api/test_webhooks.py` | No | **MISSING** |
| `tests/test_api/conftest.py` | Yes | OK |
| `tests/test_agent/test_graph.py` | Yes | OK |
| `tests/test_agent/test_routing.py` | No | **MISSING** |
| `tests/test_agent/test_validation.py` | No | **MISSING** |
| `docs/sprints/SPRINT_W{N}.md` | No `sprints/` directory | **MISSING** |

**Undocumented test files (exist but not in testing.md):**
- `test_tools/test_advanced_tools.py`
- `test_tools/test_edge_cases.py`
- `test_tools/test_edge_cases_sprint7.py`
- `test_api/test_api_auth.py`
- `test_e2e/test_e2e_lifecycle.py`
- `test_models/test_models.py`
- `test_security/test_security_audit.py`
- `test_services/test_graceful_degradation.py`
- `test_services/test_qbo_error_handling.py`
- `test_services/test_slack.py`
- `test_services/test_slack_formatting.py`
- `test_services/test_structured_logging.py`
- `test_services/test_welcome_message.py`

### B8. docs/sprint-plan.md

| Documented Claim | Exists in Tree? | Status |
|---|---|---|
| Week 1: QBO connection + health endpoint | `integrations/quickbooks.py` exists | OK |
| Week 2: 4 financial tools | All exist in `tools/` | OK |
| Week 3: anomaly, scenario, fundraising + agent | All exist | OK |
| Week 4: Slack bot + proactive alerts | `integrations/slack.py`, `services/proactive_alerts.py` exist | OK |
| Week 5: Monthly report + fundraising | `tools/monthly_report.py`, `services/monthly_report.py` exist | OK |
| Week 6: Onboarding UI | Frontend pages **do not exist** | **CONTRADICTION** — marked [x] complete but files missing |
| Week 6: Plaid connect | Marked `[ ]` incomplete | OK — consistent with "planned for later" |
| Week 7: Security audit done [x] | `test_security/test_security_audit.py` exists | OK |
| Mentions `QB_CLIENT_ID` env var name | CLAUDE.md uses `QBO_CLIENT_ID` | Naming inconsistency |
| References `docs/09-mimari-ve-gelistirme-seans-raporu.md` | Does not exist | **MISSING** reference |

---

## SECTION C: Config Consistency

### C1. pyproject.toml Scripts vs CLAUDE.md Commands

| CLAUDE.md Command | pyproject.toml Script? | Match? |
|---|---|---|
| `uv sync` | N/A (uv built-in) | OK |
| `uv run fastapi dev backend/app/main.py` | No script alias | OK — direct invocation |
| `uv run pytest` | No script alias | OK |
| `uv run pytest tests/test_tools/ -v` | No script alias | OK |
| `uv run ruff check .` | No script alias | OK |
| `uv run mypy backend/` | No script alias | OK |

**Finding:** pyproject.toml has no `[project.scripts]` section. All commands are invoked via `uv run`. This is fine but adding script aliases (e.g., `[tool.uv.scripts]`) would be a convenience improvement.

**Discrepancy:** CLAUDE.md says `uv run mypy backend/` but CI runs `uv run mypy backend/ --ignore-missing-imports`. The `--ignore-missing-imports` flag suggests strict mode isn't fully working — contradicts backend.md claim of "mypy in strict mode."

### C2. CI Workflows vs testing.md

| testing.md Specification | CI Implementation | Match? |
|---|---|---|
| CI YAML sample | Actual ci.yml | **Identical** |
| Deploy YAML sample | Actual deploy.yml | **Identical** |
| "CI: lint -> type check -> tool tests -> API tests -> coverage" (CLAUDE.md) | ci.yml runs exactly this sequence | OK |
| "Agent integration tests (nice to have)" | Not in CI | OK — documented as optional |
| "Frontend smoke tests (required before launch)" | Not in CI, no test runner installed | **GAP** |
| "add vitest or jest in Week 6" | Not added | **OVERDUE** — Week 6 tasks marked complete |

**CI gaps vs actual test files:**

| Test Directory | Files | In CI? |
|---|---|---|
| `test_tools/` | 4 test files + conftest | Yes |
| `test_api/` | 3 test files + conftest | Yes |
| `test_agent/` | 1 test file | **No** |
| `test_models/` | 1 test file | **No** |
| `test_services/` | 6 test files | **No** |
| `test_security/` | 1 test file | **No** |
| `test_e2e/` | 1 test file | **No** |

16 test files exist; CI runs tests from only 2 of 7 directories.

### C3. Environment Variable Consistency

| Env Var | CLAUDE.md | backend.md (config.py) | architecture.md | CI/Deploy | Status |
|---|---|---|---|---|---|
| `CLERK_SECRET_KEY` | Yes | Yes | Yes | No | OK |
| `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY` | Yes | No (frontend) | No | No | OK — frontend only |
| `DATABASE_URL` | Yes | Yes | Yes | No | OK |
| `ANTHROPIC_API_KEY` | Yes | Yes | Yes | No | OK |
| `QBO_CLIENT_ID` | Yes | Yes | No | No | OK |
| `QBO_CLIENT_SECRET` | Yes | Yes | No | No | OK |
| `QBO_ENVIRONMENT` | Yes | Yes | No | No | OK |
| `PLAID_CLIENT_ID` | Yes | Yes (default "") | No | No | OK |
| `PLAID_SECRET` | Yes | Yes (default "") | No | No | OK |
| `PLAID_ENV` | Yes | Yes | No | No | OK |
| `STRIPE_SECRET_KEY` | Yes | Yes | No | No | OK |
| `STRIPE_WEBHOOK_SECRET` | Yes | Yes | No | No | OK |
| `SLACK_BOT_TOKEN` | Yes | Yes | No | No | OK |
| `SLACK_SIGNING_SECRET` | Yes | Yes | No | No | OK |
| `SLACK_APP_TOKEN` | Yes | Yes (default "") | No | No | OK |
| `RAILWAY_DEPLOY_WEBHOOK_URL` | No | No | No | deploy.yml | **Missing from docs** |
| `QB_REDIRECT_URI` | sprint-plan only | No | No | No | **Inconsistent naming** — sprint uses `QB_*`, CLAUDE.md uses `QBO_*` |
| `NEXT_PUBLIC_API_URL` | No | No (frontend.md code) | No | No | Referenced in frontend.md code sample but not in env var list |

**Issues:**
1. `RAILWAY_DEPLOY_WEBHOOK_URL` used in deploy.yml but not documented anywhere.
2. `NEXT_PUBLIC_API_URL` referenced in frontend.md's API wrapper code but not in CLAUDE.md's env var list.
3. Sprint-plan uses `QB_*` prefix while CLAUDE.md and backend.md use `QBO_*` prefix — naming inconsistency across docs.

### C4. Version Consistency

| Component | pyproject.toml | package.json | CI | CLAUDE.md | Status |
|---|---|---|---|---|---|
| Python | `>=3.12` | N/A | Not pinned (relies on .python-version) | "Python 3.12" | OK but CI should pin |
| Node.js | N/A | `@types/node: "^20"` | `node-version: 20` | Not specified | OK |
| Next.js | N/A | `16.1.6` | N/A | "Next.js (App Router)" | OK |
| React | N/A | `19.2.3` | N/A | Not specified | OK |
| TypeScript | N/A | `^5` | N/A | "TypeScript strict" | OK |

**No critical version mismatches found.**

---

## Summary of Critical Findings

### Severity: HIGH (Blocks correctness or security)

| # | Finding | Location |
|---|---|---|
| H1 | `.env.example` is gitignored — safe template won't be available to new contributors | `.gitignore` line 5 |
| H2 | `backend/app/api/v1/` directory missing — all API routes documented but no route files exist | CLAUDE.md, backend.md |
| H3 | `backend/app/prompts/` directory missing — 5 prompt files documented but none exist | backend.md, agents.md |
| H4 | deploy.yml `environment` input (staging/production) is accepted but never used — all deploys are identical | `.github/workflows/deploy.yml` |
| H5 | deploy.yml has no CI gate — can deploy without tests passing | `.github/workflows/deploy.yml` |
| H6 | 12 of 16 test files not run in CI — significant test coverage gap in automation | `.github/workflows/ci.yml` |
| H7 | `frontend/.env` exists in working tree — verify not committed and properly gitignored | `frontend/.env` |

### Severity: MEDIUM (Documentation drift, tech debt)

| # | Finding | Location |
|---|---|---|
| M1 | `slack_user_map` model file missing — table defined in db.md but no SQLModel | `backend/app/models/` |
| M2 | Frontend onboarding pages missing — sprint-plan marks Week 6 onboarding [x] complete but files don't exist | `frontend/src/app/` |
| M3 | `financial_summary.py` tool undocumented in agents.md (8th tool) | `backend/app/tools/` |
| M4 | Test file structure diverges from testing.md — consolidated files vs per-tool files | `backend/tests/test_tools/` |
| M5 | `plaid-python` installed as direct dep before Plaid is needed (YAGNI) | `pyproject.toml` |
| M6 | `aiohttp` is an undocumented direct dependency | `pyproject.toml` |
| M7 | architecture.md C4 diagram mentions "Xero" which is explicitly out of scope | `docs/architecture.md` |
| M8 | No frontend test runner installed (testing.md says "add in Week 6", marked done) | `frontend/package.json` |
| M9 | mypy `--ignore-missing-imports` in CI contradicts "strict mode" claim | CI vs backend.md |
| M10 | Sprint-plan references `docs/09-mimari-ve-gelistirme-seans-raporu.md` which doesn't exist | `docs/sprint-plan.md` |

### Severity: LOW (Cleanup items)

| # | Finding | Location |
|---|---|---|
| L1 | Orphan files: `LastSummary.md`, `LastWalkthrough.md`, `ruff_report.txt` | Root directory |
| L2 | `backend/test_db.py` misplaced outside test directory | `backend/` |
| L3 | `frontend/.clerk/.tmp/` not gitignored | `frontend/` |
| L4 | `frontend/tsconfig.tsbuildinfo` not gitignored | `frontend/` |
| L5 | No `docs/sprints/` directory for sprint reports | `docs/` |
| L6 | `RAILWAY_DEPLOY_WEBHOOK_URL` and `NEXT_PUBLIC_API_URL` not in documented env vars | CLAUDE.md |
| L7 | `QB_*` vs `QBO_*` env var naming inconsistency between sprint-plan and other docs | Multiple docs |
| L8 | `docs/package-changes.md` and `docs/sprint-plan.md` not in CLAUDE.md documentation map | CLAUDE.md |
| L9 | `backend/app/utils/` exists but is empty (only `__init__.py`) | `backend/app/utils/` |
| L10 | deploy.yml curl lacks `-f` flag — HTTP errors silently succeed | `.github/workflows/deploy.yml` |

---

## Recommended Next Steps

1. **Fix .gitignore** — Remove `.env.example` from gitignore, add missing patterns.
2. **Reconcile api/v1/ and prompts/** — Either create the directories or update docs to match reality.
3. **Add missing tests to CI** — At minimum, add `test_services/` and `test_security/` to the CI pipeline.
4. **Fix deploy.yml** — Wire up the `environment` input, add CI dependency, add `-f` to curl.
5. **Update CLAUDE.md documentation map** — Add `sprint-plan.md`, `package-changes.md`, remove non-existent entries.
6. **Audit the "completed" sprint items** — Several Week 6-7 items are marked complete but corresponding files don't exist.
7. **Clean up orphan files** — Remove or gitignore `LastSummary.md`, `LastWalkthrough.md`, `ruff_report.txt`, `backend/test_db.py`.
