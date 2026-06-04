# Agent Architecture

## Design Philosophy

Single supervisor agent with deterministic LangGraph tools. Not multi-agent.

**Why single agent for MVP:** All 7 tools fit in one context window. Multi-agent adds orchestration protocol, inter-agent messaging, state synchronization — complexity that delivers zero extra value at 10 tenants. When a single agent's context window can't handle a customer's full financial picture (hundreds of accounts, multi-entity), that's when you split. Not before.

**Why LangGraph tools (not raw Python):** LangGraph tools ARE pure Python functions — decorated with `@tool` so the agent can discover and call them. The agent (Claude) decides which tools to call and in what order based on the user's question. The function itself does deterministic math. No LLM inside the function.

**Integration Scope:** The agent operates exclusively on financial data snapshots ingested from QuickBooks Online. All tools are designed for QBO structures, with no banking or other third-party aggregator dependencies.

## Graph Structure

```
START
  ↓
[receive_input]
  Slack message | scheduled trigger | webhook
  ↓
[load_financial_data]
  Read latest financial_snapshots from DB for this tenant
  ↓
[agent_loop]  ←────────────────────────────┐
  Claude selects tool(s) → calls them →    │
  receives results → decides if more       │
  tools needed                             │
  ↓ (needs more tools)  ────────────────────┘
  ↓ (done)
[cross_validate]
  Compare any LLM-generated numbers against tool outputs
  If discrepancy > 1%: log warning, use tool number
  If discrepancy > 10%: log error, flag for review
  ↓
[format_output]
  Structure response as Slack Block Kit message
  ↓
[send_to_slack]
  Post to user's channel or thread
  ↓
[log_run]
  Save to agent_runs table:
  tools_called, model_used, tokens, cost, duration, output
  ↓
END
```

The `agent_loop` node is where Claude reasons. It has access to all tools and calls them as needed. This is a standard ReAct loop in LangGraph — the agent observes tool outputs and decides the next action.

## State Schema

```python
from typing import TypedDict, Literal
from decimal import Decimal

class CFOAgentState(TypedDict):
    # Input
    tenant_id: str
    trigger_type: Literal["scheduled", "slack_message", "webhook", "manual"]
    trigger_payload: dict  # original message or trigger params

    # Financial data loaded from DB
    financial_data: dict | None  # latest snapshots

    # Accumulated tool results
    tool_results: dict  # keyed by tool name

    # LLM tracking
    model_used: str
    messages: list  # LangGraph message history

    # Cross-validation
    discrepancies: list[dict]  # {field, tool_value, llm_value, severity}

    # Output
    slack_message: dict | None  # Block Kit formatted

    # Observability
    tools_called: list[str]
    tokens_input: int
    tokens_output: int
    duration_ms: int
```

## Model Routing

The router selects Claude model before the agent loop starts. Based on trigger type and detected complexity.

```python
def select_model(trigger_type: str, user_message: str = "") -> str:
    # Opus triggers — complex reasoning keywords
    OPUS_TRIGGERS = {"should i", "recommend", "strategy", "what if", "scenario",
                     "compare", "trade-off", "fundraise", "investor"}
    # Sonnet triggers — report/document keywords
    SONNET_TRIGGERS = {"report", "summary", "document", "analyze", "deep dive",
                       "breakdown", "detail"}

    msg_lower = user_message.lower()

    if trigger_type == "scheduled":
        return "claude-sonnet-4-5-20250514"  # reports are always Sonnet

    if any(t in msg_lower for t in OPUS_TRIGGERS):
        return "claude-opus-4-6-20250514"

    if any(t in msg_lower for t in SONNET_TRIGGERS):
        return "claude-sonnet-4-5-20250514"

    return "claude-haiku-4-5-20250301"  # default for Slack chat
```

**Cost guidance:**
| Model | Use Case | Frequency | Cost |
|-------|----------|-----------|------|
| Haiku 4.5 | Slack Q&A, formatting | ~80% of calls | $0.80/$4 per 1M tokens |
| Sonnet 4.5 | Reports, standard analysis | ~15% of calls | $3/$15 per 1M tokens |
| Opus 4.6 | Complex reasoning, scenarios | ~5% of calls | $15/$75 per 1M tokens |

## Tool Specifications

All tools follow the same pattern:
- Pure function: same input → same output, always
- Pydantic input/output models with full type hints
- `Decimal` for all financial amounts
- Polars for data transformations where applicable
- Unit tested with known financial data (see testing.md)
- Decorated with `@tool` for LangGraph registration

### burn_rate

**File:** `backend/app/tools/burn_rate.py`

**Input:** Monthly P&L data (3-12 months), current cash position.

**Output:**
```python
class BurnRateResult(BaseModel):
    net_burn_monthly: Decimal       # Total Expenses - Total Revenue
    gross_burn_monthly: Decimal     # Total Expenses (ignoring revenue)
    burn_multiple: Decimal | None   # Net Burn / Net New ARR (SaaS only)
    trend: Literal["increasing", "stable", "decreasing"]
    trend_slope: Decimal            # Linear regression slope
    period_months: int              # How many months of data used
```

**Calculations:**
- Net burn per month from P&L: sum(expenses) - sum(revenue)
- Weighted average: exponential decay, recent months weighted 2x
- Trend: linear regression slope over available months
  - slope > 5% of mean → "increasing"
  - slope < -5% of mean → "decreasing"
  - else → "stable"

### runway

**File:** `backend/app/tools/runway.py`

**Input:** Current cash balance, monthly net burn rate (from burn_rate tool).

**Output:**
```python
class RunwayResult(BaseModel):
    runway_months: Decimal
    cash_balance: Decimal
    monthly_net_burn: Decimal
    runway_status: Literal["critical", "warning", "monitor", "healthy"]
    cash_zero_date: date | None     # Projected date cash hits zero
```

**Thresholds:**
- < 3 months → `critical`
- < 6 months → `warning`
- < 12 months → `monitor`
- ≥ 12 months → `healthy`

### cash_forecast

**File:** `backend/app/tools/cash_forecast.py`

**Input:** 13+ weeks of historical weekly cash flow data.

**Output:**
```python
class CashForecastResult(BaseModel):
    weeks: list[WeekProjection]  # 13 weeks forward
    zero_cash_week: int | None   # Week number where balance hits 0

class WeekProjection(BaseModel):
    week_start: date
    projected_inflow: Decimal
    projected_outflow: Decimal
    projected_balance: Decimal
```

**Method:** Linear trend extrapolation from historical weekly totals. Separate trend lines for inflow and outflow. Flags the first week where projected_balance ≤ 0.

### anomaly

**File:** `backend/app/tools/anomaly.py`

**Input:** Monthly financial data by category (6+ months preferred, 3 minimum).

**Output:**
```python
class AnomalyResult(BaseModel):
    anomalies: list[Anomaly]
    scan_period_months: int

class Anomaly(BaseModel):
    category: str               # Expense category name
    current_amount: Decimal
    historical_mean: Decimal
    z_score: Decimal
    severity: Literal["warning", "critical"]
    description: str            # Human-readable explanation
```

**Method:** Z-score per category per month.
- Mean and standard deviation over historical period (rolling window)
- Z-score = (current_value - mean) / std_dev
- |Z-score| > 2.0 → flagged (this is standard statistical convention — 2σ captures 95.4% of normal variation)
- |Z-score| > 3.0 → critical
- Also flag: new categories not seen before, disappeared categories, single vendor > 30% of category

**Why 2.0 threshold:** Standard statistical practice. 1.5 produces too many false positives (annoying alerts). 3.0 catches only extreme outliers (misses real issues). 2.0 is the starting point — tune based on customer feedback.

### scenario

**File:** `backend/app/tools/scenario.py`

**Input:** Current financial state + list of parameter changes.

**Output:**
```python
class ScenarioResult(BaseModel):
    current_runway: Decimal
    new_runway: Decimal
    delta_runway: Decimal
    current_burn: Decimal
    new_burn: Decimal
    delta_burn: Decimal
    changes_applied: list[ScenarioChange]

class ScenarioChange(BaseModel):
    type: Literal["hire", "fire", "revenue_change", "new_expense", "cut_expense"]
    description: str
    monthly_impact: Decimal   # Positive = cost increase, Negative = savings
```

**Method:** Pure arithmetic. Take current burn model, apply changes, recalculate runway. No forecasting, no regression — just simple addition/subtraction to show the immediate impact.

**Example:** "Hire 2 engineers at $12K/mo each" → monthly_impact = +$24K → new burn, new runway.

### fundraising

**File:** `backend/app/tools/fundraising.py`

**Input:** Revenue data (6+ months), burn data, cash position.

**Output:**
```python
class FundraisingResult(BaseModel):
    readiness_score: int        # 0-100
    metrics: FundraisingMetrics
    gaps: list[str]             # What to improve

class FundraisingMetrics(BaseModel):
    mrr: Decimal | None
    mrr_growth_rate: Decimal | None   # MoM %
    arr: Decimal | None
    burn_multiple: Decimal | None
    runway_months: Decimal
    gross_margin: Decimal | None
```

**Scoring (0-100, weighted):**
- Runway ≥ 6 months: 25 points
- MRR growth > 15% MoM: 25 points
- Burn multiple < 2x: 20 points
- Gross margin > 60%: 15 points
- Revenue exists and growing: 15 points

Gaps = list of metrics that didn't meet threshold, with specific recommendation text.

### monthly_report

**File:** `backend/app/tools/monthly_report.py`

**Input:** Tenant ID + month. Internally calls all other tools.

**Output:**
```python
class MonthlyReportData(BaseModel):
    period: str                          # "2026-03"
    burn_rate: BurnRateResult
    runway: RunwayResult
    cash_forecast: CashForecastResult
    anomalies: AnomalyResult
    fundraising: FundraisingResult
    executive_summary: str | None        # Filled by Claude Sonnet after tool execution
```

This tool aggregates. It calls the other 5 tools, bundles the results, and passes them to Claude Sonnet for narrative generation.

## Cross-Validation

Built into the agent graph, runs after the agent loop completes.

```python
def cross_validate(state: CFOAgentState) -> CFOAgentState:
    """Compare LLM-generated numbers against tool outputs."""
    tool_numbers = extract_numbers(state["tool_results"])
    llm_numbers = extract_numbers_from_text(state["messages"][-1].content)

    discrepancies = []
    for field, tool_val in tool_numbers.items():
        if field in llm_numbers:
            llm_val = llm_numbers[field]
            pct_diff = abs(tool_val - llm_val) / tool_val if tool_val else 0
            if pct_diff > 0.01:  # > 1% difference
                discrepancies.append({
                    "field": field,
                    "tool_value": tool_val,
                    "llm_value": llm_val,
                    "pct_diff": pct_diff,
                    "severity": "error" if pct_diff > 0.10 else "warning"
                })

    state["discrepancies"] = discrepancies
    return state
```

**Rule: Tools always win on numbers.** If Claude says runway is 5.2 months but the tool calculated 4.8, the output uses 4.8. Claude's value is in the interpretation and narrative, not the arithmetic.

## Prompts

See `backend/app/prompts/` directory. Each file is a plain text template with `{variable}` placeholders.

**system_base.txt** — Appended to every prompt:
- "You are the CFO intelligence layer for {company_name}"
- "All numbers in tool_results are verified. Use them exactly. Do not recalculate."
- "Be concise. Founders are busy."

**slack_chat.txt** — Haiku conversations:
- Keep responses under 200 words
- Lead with the answer, then supporting data
- Use Slack formatting (bold, code blocks)

**report_generation.txt** — Sonnet monthly reports:
- Executive summary first (3-4 sentences)
- Then metrics sections
- End with 1-2 actionable recommendations

**scenario_analysis.txt** — Opus what-if analysis:
- Acknowledge the scenario clearly
- Present numbers from scenario tool
- Provide strategic context and trade-offs
- Never say "you should" — say "the data suggests"

**anomaly_interpretation.txt** — Sonnet anomaly explanation:
- State what was flagged and why
- Provide possible explanations (not conclusions)
- Suggest what to investigate
