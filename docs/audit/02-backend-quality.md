# Backend Quality Audit — Flowytics

**Date:** 2026-03-28
**Auditor:** Claude Sonnet 4.6
**Scope:** backend/ directory (config, auth, DB, API, integrations, services, agent, tools, prompts)
**Legend:** ✅ Done & working | ⚠️ Partial | ❌ Missing or broken | 🔴 Broken (would fail in production)

---

## SECTION D: Sprint Progress Verification

### Week 1 — Infrastructure & QBO

| Item | Status | Notes |
|------|--------|-------|
| FastAPI app starts with proper router registration | ✅ | `main.py` registers `me`, `quickbooks`, `stripe`, `slack` routers. APScheduler starts in lifespan. |
| Clerk auth middleware extracts `user_id` and `org_id` from JWT | ✅ | `auth.py` calls Clerk session verify endpoint, extracts `sub` → `user_id` and `org_id`. Returns 401 if org absent. |
| QBO OAuth flow: auth URL + callback + token persistence | ✅ | `integrations/quickbooks.py` has `generate_auth_url`, `handle_callback` (Fernet-encrypted token storage). Upserts integration row. |
| QBO data pull: P&L, Balance Sheet, Cash Flow | ✅ | `get_profit_and_loss`, `get_balance_sheet`, `get_cash_flow` all implemented using `_fetch_report` helper. Catches 401 as `TokenExpiredError`. |
| Sync service: QBO → `financial_snapshots` table | ✅ | `services/sync.py` pulls all three reports and persists three `FinancialSnapshot` rows per sync, updates `last_synced_at`. |
| Manual sync endpoint: `POST /api/v1/quickbooks/sync` | ✅ | Endpoint is `/api/v1/quickbooks/sync`, authenticated, calls `sync_tenant`. |

### Week 2 — Financial Tools

| Item | Status | Notes |
|------|--------|-------|
| `calculate_burn_rate` (net, gross, burn multiple) | ⚠️ | Implemented and correct. `burn_multiple` is permanently `None` — ARR logic explicitly deferred. Spec says this is SaaS-only, acceptable. |
| `calculate_runway` (cash / net burn) | ✅ | Correct. Handles zero/negative cash. Returns `9999` for zero-burn. |
| `cash_forecast_13_week` | ⚠️ | 13 weeks generated. Flat projection (no trend extrapolation) — comment says "MVP". The `week_start` label is off by one: it uses start-of-week date but the projected_balance already includes that week's flows (end-of-week balance). Minor labeling bug. |
| `get_financial_summary` (`parse_qbo_to_financial_summary`) | 🔴 | **Critical stub.** Parses `pl_data["monthly_data"]` — a custom pre-processed format that does not exist in real QBO responses. Real QBO `ProfitAndLoss` JSON (`Rows.Row[]` nested structure) is read into `pl_rows` at line 16 but then **never used**. Falls through to return empty `FinancialSummary`. The entire analytics pipeline returns zeros against real QBO data. |
| All tools use `Decimal`, never `float` | ✅ | All monetary values use `Decimal` throughout. `statistics.mean/stdev` results are wrapped via `Decimal(str(...))` before use. |

### Week 3 — Anomaly & Scenario

| Item | Status | Notes |
|------|--------|-------|
| `detect_anomalies` (z-score based) | ⚠️ | Z-score logic correct. Missing: new categories not seen before, disappeared categories, single vendor >30% of category — all listed in spec but not implemented. |
| `scenario_simulate` (hire/fire/revenue/expense) | ✅ | All scenario types supported via `ScenarioChange`. Pure arithmetic. Handles zero/negative burn correctly. |
| Claude integration: NL query → tool call → NL response | ⚠️ | Graph wiring is correct but the agent receives no financial data. See E.2 for details. |

### Week 4+ — Slack & Reports

| Item | Status | Notes |
|------|--------|-------|
| Slack bot receives and responds to messages | ✅ | `app_mention` event handled by Bolt, offloaded to `process_slack_message`. Block Kit formatting complete. |
| Proactive alert scheduler | ⚠️ | Scheduler configured (daily 9am). Rules for runway <4mo, burn spike >25%, critical anomalies. Will return no alerts in production because `parse_qbo_to_financial_summary` returns empty — see QBO parser bug above. |
| Monthly report generation | ⚠️ | LangChain + Sonnet narrative generation wired correctly. Same QBO parser bug blocks it in production. |
| Fundraising readiness tool | ⚠️ | Implemented. Max achievable score is 85/100 (15-point gross margin component always returns `None`). See E.1. |

---

## SECTION E: Code Quality

### E.1 Financial Tools

#### `calculate_burn_rate` (`tools/burn_rate.py`)

| Check | Result | Detail |
|-------|--------|--------|
| Decimal everywhere | ✅ | All arithmetic uses `Decimal`. Weights (`Decimal("1")`, `Decimal("2")`) explicit. |
| Edge cases (zero, empty, single month) | ✅ | n=0 → return zeros. n=1 → denominator=0 → slope=0 → "stable" (correct). |
| Math correct | ✅ | Weighted average (older = 1×, newer half = 2×). Linear regression slope formula is correct. Trend thresholds (5% of mean_burn) match spec. |
| Error messages | ⚠️ | No explicit errors thrown; returns defaults silently. Acceptable for a tool used in a pipeline. |

**Note:** `burn_multiple` is permanently `None`. The spec allows this ("SaaS only"), but it means the fundraising scoring will never reach 100/100 from this source.

---

#### `calculate_runway` (`tools/runway.py`)

| Check | Result | Detail |
|-------|--------|--------|
| Decimal everywhere | ✅ | |
| Edge cases | ✅ | Zero/negative cash → critical/0. Zero/negative burn → healthy/9999. |
| Math correct | ✅ | `runway_months = cash / net_burn`. Status thresholds match spec (<3 critical, <6 warning, <12 monitor). |
| Error messages | ✅ | Wraps `zero_date` calculation in try/except to handle edge dates. |

---

#### `calculate_cash_forecast` (`tools/cash_forecast.py`)

| Check | Result | Detail |
|-------|--------|--------|
| Decimal everywhere | ✅ | `weeks_per_month = Decimal("4.33")`. All arithmetic clean. |
| Edge cases | ✅ | Empty financials → empty list. Fewer than 3 months → uses available data. |
| Math correct | ⚠️ | Flat projection (no trend slope) is a documented MVP simplification. **Week label bug:** `week_start` reflects the start of the week but `projected_balance` is already the end-of-week balance (accumulation happens before the WeekProjection is built). Week 1 shows today's date with the balance after this week's flows. |
| Error messages | ✅ | Returns `CashForecastResult(weeks=[], zero_cash_week=None)` on empty input. |

---

#### `calculate_anomalies` (`tools/anomaly.py`)

| Check | Result | Detail |
|-------|--------|--------|
| Decimal everywhere | ✅ | `statistics.mean/stdev` called on Decimal lists; results wrapped via `Decimal(str(...))`. |
| Edge cases | ✅ | <3 months → empty result. stdev=0 → falls back to absolute-change heuristic (>50% increase AND >$1K). |
| Math correct | ✅ | Z-score formula correct. |2σ| threshold and |3σ| critical match spec. |
| Error messages | ✅ | Returns empty AnomalyResult, not an exception. |

**Missing features from spec (not bugs, just unimplemented):**
- New categories not seen before
- Disappeared categories
- Single vendor >30% of category

---

#### `calculate_scenario_impact` (`tools/scenario.py`)

| Check | Result | Detail |
|-------|--------|--------|
| Decimal everywhere | ✅ | |
| Edge cases | ✅ | Empty financials handled separately. Zero/negative new_burn → 9999 runway. |
| Math correct | ✅ | Pure arithmetic: adds monthly_impact to current burn, recalculates runway from cash. |
| Error messages | ✅ | Returns synthetic result on empty data. |

---

#### `calculate_fundraising_readiness` (`tools/fundraising.py`)

| Check | Result | Detail |
|-------|--------|--------|
| Decimal everywhere | ✅ | |
| Edge cases | ✅ | Empty financials → 0 score, descriptive gap. Single month → mrr_growth_rate = None, handled. |
| Math correct | ❌ | **Scoring bug:** `gross_margin` is hardcoded to `None` (line 88: `gross_margin=None  # MVP excludes COGS`). The gross margin component (15 points per spec) is never evaluated. Maximum achievable score is **85/100**, but the function implies 100 is possible. |
| Error messages | ✅ | Gaps list provides human-readable explanations. |

**Additional note:** `burn_multiple` calculation uses `net_burn / net_new_arr`. If `net_new_arr < 0` (revenue declining), the condition `net_new_arr > 0` correctly returns `None`. ✅

---

#### `generate_monthly_report_data` (`tools/monthly_report.py`)

| Check | Result | Detail |
|-------|--------|--------|
| Decimal everywhere | ✅ | Delegates to other tools. |
| Edge cases | ✅ | Delegates to other tools. |
| Math correct | ⚠️ | Calls `calculate_cash_forecast.invoke({"summary": summary, "runway": runway})` but `calculate_cash_forecast` only accepts `summary`. The extra `runway` kwarg is silently ignored by LangChain's tool invocation. Not a runtime error, but unexpected. |
| Error messages | ✅ | Each sub-tool handles its own edge cases. |

---

#### `parse_qbo_to_financial_summary` (`tools/financial_summary.py`)

| Check | Result | Detail |
|-------|--------|--------|
| Decimal everywhere | ✅ | |
| QBO JSON parsing | 🔴 | **Critical.** `pl_rows = pl_data.get("Rows", {}).get("Row", [])` is read at line 16 but **never used**. The function immediately checks for `pl_data["monthly_data"]` — a custom test fixture format. Real QBO `ProfitAndLoss` JSON does not contain `monthly_data`. Falls through to `return FinancialSummary(current_cash_balance=Decimal("0"), monthly_financials=[])`. Every downstream tool (burn rate, runway, anomalies, alerts, reports) receives empty data against real QBO. |
| Error messages | ✅ | Gracefully handles malformed rows via try/except. |

---

### E.2 Agent Architecture

#### Graph Structure

**Specified:**
```
START → receive_input → load_financial_data → agent_loop → cross_validate → format_output → send_to_slack → log_run → END
```

**Actual:**
```
START → select_model → agent → (tools → agent)* → cross_validate → END
```

| Check | Status | Detail |
|-------|--------|--------|
| Graph structure | ⚠️ | Simplified but coherent. Missing explicit `load_financial_data`, `format_output`, `send_to_slack`, and `log_run` nodes — these are handled externally in `slack_agent_runner.py` before/after graph invocation. |
| **Financial data flow** | 🔴 | **Critical.** `slack_agent_runner.py` invokes the graph with `{"messages": [("user", clean_text)]}` — no financial data. `AgentState.financial_summary` is declared but never populated. The `call_model` node checks `state.get("financial_summary")` but it is always `None`. Tools expect `FinancialSummary` as an argument — the agent would need to call `parse_qbo_to_financial_summary` first, but that tool is not in `active_tools`. There is no path for the agent to acquire real financial data during a conversation. |

---

#### Model Routing

| Check | Status | Detail |
|-------|--------|--------|
| Model routing works | ⚠️ | Logic is correct: `select_model` node runs first, sets `recommended_model`. `call_model` reads it. Haiku for greetings, Opus for scenarios, Sonnet default. |
| Model IDs correct | ❌ | All three model IDs are incorrect. `"claude-4-6-opus-latest"`, `"claude-4-5-haiku-latest"`, `"claude-4-6-sonnet-latest"` are not valid Anthropic model IDs. Correct IDs per CLAUDE.md/agents.md: `claude-opus-4-6-20250514`, `claude-sonnet-4-5-20250514`, `claude-haiku-4-5-20251001`. Same invalid ID used in `monthly_report.py` (`"claude-4-6-sonnet-latest"`). These will fail at runtime when LangChain attempts to call the API. |

---

#### Tool Descriptions

| Check | Status | Detail |
|-------|--------|--------|
| Tool descriptions sufficient | ✅ | All 7 tools have docstrings. `system_base.txt` has a routing table mapping user intent to tool name. Clear and unambiguous. |
| Tool inputs constructable by LLM | 🔴 | The agent is expected to call tools with a `FinancialSummary` argument it doesn't have. Since no financial data is loaded into state, the agent cannot call any financial tool with real data. This is the same data flow bug as above. |

---

#### Cross-Validation

| Check | Status | Detail |
|-------|--------|--------|
| Cross-validation logic | ⚠️ | Uses regex `\b\d{2,}(?:\.\d+)?\b` to compare numbers in LLM output against tool JSON dumps. The approach is directionally correct but fragile: formatting differences (`$12,500` vs `12500.00`) will cause false hallucination flags. Year numbers (e.g., `2026`) are explicitly excluded. |
| Correction mechanism | ⚠️ | Correction injects a `HumanMessage(name="system_validator")` into the conversation, routing back to the agent. Functional, but LangChain may handle `name=` on HumanMessage inconsistently. |
| Infinite loop guard | ❌ | No maximum retry count. If the agent repeatedly generates a number not in tool output (e.g., a computed percentage), the graph could loop indefinitely. |

---

### E.3 QBO Integration

| Check | Status | Detail |
|-------|--------|--------|
| OAuth complete | ✅ | Auth URL generation, code exchange, token persistence all working. State JWT used to survive OAuth roundtrip. |
| Token refresh before expiry | ✅ | `auto_refresh_token` uses a 50-minute window (Intuit tokens valid 60 min). Refreshes proactively. Handles refresh failure by marking integration `disconnected`. |
| Graceful handling of QBO downtime | ✅ | `TokenExpiredError` and `IntegrationError` are propagated through the stack. Sync service marks integration status appropriately. `slack_agent_runner.py` catches both and sends user-facing error blocks. |
| FERNET_KEY fallback | ⚠️ | If `FERNET_KEY` is unset, derives encryption key from `CLERK_SECRET_KEY` via SHA256. Logs a warning. Acceptable for dev; must be set in production. |
| Tenant isolation in `get_qbo_client` | ⚠️ | Query is `WHERE provider_connection_id = realm_id AND provider = 'quickbooks'` — no `tenant_id` filter. QuickBooks realm IDs are globally unique so collision risk is near-zero, but this violates the "every query filters by tenant_id" rule in CLAUDE.md. |

---

### E.4 Security

| Check | Status | Detail |
|-------|--------|--------|
| Protected endpoints check auth | ✅ | `GET /me`, `GET /quickbooks/auth`, `POST /quickbooks/sync`, `POST /stripe/create-checkout-session`, `GET /slack/install` all use `Depends(get_current_user)`. |
| `tenant_id` from JWT, not request body | ✅ | `sync_tenant(user["org_id"], session)` — org_id from verified JWT claim only. |
| OAuth callback endpoints (no auth) | ⚠️ | `GET /quickbooks/callback` and `GET /slack/oauth_redirect` have no `Depends(get_current_user)` — by design, as OAuth callbacks come from the provider. Both validate the `state` parameter as a JWT signed with `CLERK_SECRET_KEY[:32]`. Using a slice of the signing key is nonstandard; use `FERNET_KEY` or a dedicated OAuth state secret. |
| `POST /stripe/webhook` (no auth) | ✅ | No bearer auth by design. Validates Stripe signature via `verify_webhook`. Correct. |
| **`POST /slack/trigger_monthly_report`** | ❌ | **Authorization bypass.** Endpoint accepts `tenant_id: str` as a query param. Auth check only confirms the user is authenticated, not that they belong to the requested tenant. Any authenticated user can trigger a monthly report for any tenant. |
| `POST /slack/events` (no auth) | ✅ | Slack Bolt handles signature verification. Correct. |
| Hardcoded fallback credentials | ⚠️ | `slack_app = AsyncApp(token=settings.SLACK_BOT_TOKEN or "xoxb-dummy-token", signing_secret=... or "dummy-secret")`. Fallback prevents startup crash in dev but `"dummy-secret"` is a real string Bolt will use for signature verification, meaning any request with the matching dummy signature would pass. Must not reach production without real values. |
| Secrets from env only | ✅ | `pydantic-settings` with `.env`. No hardcoded production secrets. |

---

### E.5 Prompts

#### `system_base.txt`

| Check | Status | Detail |
|-------|--------|--------|
| Slack-native formatting | ✅ | Explicitly prohibits `#/##` headers, markdown tables, code blocks for financial data. Specifies `*bold*` and bullet points. |
| Financial advice boundaries | ✅ | `<financial_advice_boundary>` section is thorough: CORRECT/INCORRECT patterns, explicit "never say you should". |
| Tool routing table | ✅ | Intent-to-tool mapping is clear and complete for all 7 tools. |
| Proactive alert thresholds | ⚠️ | Thresholds in prompt (`cash below 2x monthly burn`, `runway below 6 months`) differ from thresholds hardcoded in `proactive_alerts.py` (`runway < 4 months`, `burn spike > 25%`). No consistency issue for the LLM, but the thresholds are inconsistent between the scheduler rule engine and the prompt guidance. |

---

#### `report_generation.txt`

| Check | Status | Detail |
|-------|--------|--------|
| Output format | ✅ | Requires raw JSON with `executive_summary` and `key_consideration`. No wrappers. `monthly_report.py` parses with `json.loads`. |
| Financial advice boundary | ✅ | CORRECT/INCORRECT examples explicit. No directives. |
| Data accuracy rule | ✅ | "Every number you quote must exist in the provided payload." |
| Prompt injection risk | ⚠️ | `metrics_payload = report_data.model_dump_json()` is passed as the human message body. If a founder's company name or a category name contains injected instructions, they would be in the payload. Low risk in practice (it's a JSON blob). |

---

#### `scenario.txt`, `anomaly.txt`, `fundraising.txt`

| Check | Status | Detail |
|-------|--------|--------|
| No markdown tables | ✅ | All three use bullet/field format. `scenario.txt` explicitly says "(tables render inconsistently in Slack)". |
| Financial advice boundary | ✅ | All three have CORRECT/INCORRECT patterns. `fundraising.txt` has SAFETY RESTRICTION with zero-guarantee language. |
| Tool descriptions match signatures | ✅ | Tool routing table in `system_base.txt` matches actual function names. |
| Prompt injection | ⚠️ | User Slack messages are passed directly as HumanMessage content. A crafted message could attempt to override the system prompt. No sanitization layer. Standard LLM risk — mitigated by the fact that the agent has no access to other tenants' data in context. |

---

## Summary: Critical Issues Requiring Immediate Fix

| # | Severity | Location | Issue |
|---|----------|----------|-------|
| 1 | 🔴 Critical | `tools/financial_summary.py` | QBO JSON parser is a stub. Real QBO data is never parsed. Every analysis returns zeros in production. |
| 2 | 🔴 Critical | `services/slack_agent_runner.py` | Financial data not loaded before graph invocation. Agent graph starts with no financial context. Tools cannot receive `FinancialSummary`. |
| 3 | 🔴 Critical | `agent/select_model.py`, `services/monthly_report.py`, `agent/graph.py` | All model IDs are invalid: `"claude-4-6-sonnet-latest"`, `"claude-4-5-haiku-latest"`, `"claude-4-6-opus-latest"`. Will raise API errors at runtime. Correct IDs: `claude-sonnet-4-5-20250514`, `claude-haiku-4-5-20251001`, `claude-opus-4-6-20250514`. |
| 4 | ❌ High | `api/v1/slack.py:114` | `trigger_monthly_report` endpoint accepts any `tenant_id` without verifying the caller belongs to that tenant. |
| 5 | ❌ High | `agent/cross_validate.py` | No maximum retry count on the correction loop. Can loop indefinitely if computed percentages or reformatted numbers trigger false hallucination flags. |
| 6 | ❌ Medium | `tools/fundraising.py:88` | `gross_margin` hardcoded to `None`; 15 scoring points are permanently unreachable. Max score is 85, not 100. The function implies otherwise. |
| 7 | ⚠️ Medium | `services/monthly_report.py:117` | `trigger_type="scheduled_report"` is not a valid value for the `AgentRun.trigger_type` CHECK constraint (`scheduled`, `slack_message`, `webhook`, `manual`). Will cause a DB constraint violation at runtime. |
| 8 | ⚠️ Medium | `models/integration.py:9`, `models/financial_snapshot.py:11` | Both model comments say `# CHECK: codat, plaid` — stale from when Codat was used. Correct values are `quickbooks` and `plaid`. Not a runtime bug but the model comments are misleading. |
| 9 | ⚠️ Medium | `config.py:25-26` | `CODAT_API_KEY` and `CODAT_BASE_URL` settings still present. Codat was dropped. Dead config. |
| 10 | ⚠️ Low | `integrations/quickbooks.py:146` | `get_qbo_client` queries by `realm_id` without `tenant_id` filter. Violates CLAUDE.md rule 6 ("NEVER query DB without tenant scope"). Low risk since QBO realm IDs are globally unique. |

---

## What Is Working Well

- **Auth layer:** Clerk JWT verification is clean. `org_id` extracted from JWT, never from request body. Deps pattern correct.
- **Middleware:** Correlation ID propagation, structured JSON logging, security headers (CSP, X-Frame, HSTS precursor) are production-grade.
- **QBO OAuth + token refresh:** Fernet encryption, 50-min proactive refresh, graceful disconnect handling — solid.
- **Sync service:** Clean separation of fetch and persist. Correct error state transitions (`active` → `disconnected` on token failure, `error` on other failures).
- **Slack formatting:** Block Kit formatting is thorough and well-structured. Handles long text splitting, stale data banners, error blocks, monthly report layout.
- **Proactive alerts service:** Data freshness gates, disconnection detection, stale data warnings — defensively written.
- **System prompt:** Well-structured, enforces financial advice boundaries, prohibits Slack-incompatible markdown, requires tool use for all numbers.
- **Burn rate + runway + scenario math:** All correct. Decimal discipline maintained. Edge cases handled.
- **Onboarding welcome:** Idempotent exactly-once delivery via `onboarding_completed` flag. ✅
